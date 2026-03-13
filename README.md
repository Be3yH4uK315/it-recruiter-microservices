# IT Recruiter Platform

Полнофункциональная платформа подбора IT кандидатов на основе гибридного поиска (Elasticsearch + Milvus), Telegram бота и микросервисной архитектуры с гарантией доставки событий.

## Обзор

IT Recruiter - масштабируемая SaaS платформа для подбора IT специалистов:

**Для кандидатов**: Telegram бот с FSM для создания профилей (опыт, навыки, проекты, файлы)

**Для работодателей**: Поиск кандидатов через:

- Гибридный поиск (Elasticsearch BM25 + Milvus semantic search)
- RRF (Reciprocal Rank Fusion) для объединения результатов
- L2 переранжирование с Cross-Encoder + multiplicative scoring

**Для системы**: Надежная микросервисная архитектура с:

- Outbox pattern для гарантии доставки событий
- Circuit Breaker для защиты от каскадных отказов
- Идемпотентность для безопасных повторов
- Структурированное логирование и трейсинг

## Архитектура

```
┌────────────────────────────────────────┐
│    Telegram Bot (aiogram 3.5)          │
│ Кандидаты и Работодатели (Двурольный)  │
└────────────────┬───────────────────────┘
                 │
┌────────────────┴──────────────────────┐
│      API Gateway (Nginx reverse)      │
│       Маршрутизация + SSL/TLS         │
└────┬──────┬──────────┬──────────┬─────┘
     │      │          │          │
     ▼      ▼          ▼          ▼
┌────────────────────────────────────┐
│  6 Микросервисов (FastAPI 0.118.0) │
├──────────┬──────────┬──────────────┤
│   Auth   │Candidate │  Employer    │
│          │          │              │
│  Search  │   Bot    │    File      │
└──────┬───┴──────────┴─────────┬────┘
       │                        │
    ┌──┴──────────┬─────────────┴──┐
    │             │                │
    ▼             ▼                ▼
┌──────────┐ ┌────────────┐  ┌──────────┐
│PostgreSQL│ │  RabbitMQ  │  │ Milvus   │
│   (15)   │ │  (Events)  │  │(Vectors) │
└──────────┘ └────────────┘  └──────────┘
    │
    ▼
┌──────────────────┐
│ Elasticsearch    │
│  (Lexical idx)   │
└──────────────────┘
    │
    ▼
┌──────────────────┐
│ Redis (FSM)      │
│ S3/MinIO(Files)  │
└──────────────────┘
```

## Микросервисы

### 🔍 Search Service - Гибридный поиск (основной)

**Главная инновация**: Параллельный поиск в Elasticsearch (лексический) и Milvus (семантический) с RRF объединением и L2 переранжированием через Cross-Encoder.

Архитектура поиска (4 этапа):

1. **Параллельный гибридный поиск**: ES (BM25) + Milvus (768-dim embeddings)
2. **RRF (Reciprocal Rank Fusion)**: нормализует scores и объединяет результаты
3. **Top-K selection**: отбор RERANK_TOP_K кандидатов для переранжирования
4. **L2 Multiplicative Scoring**: Cross-Encoder + факторы (навыки, опыт, локация, зарплата, английский)

**Multiplicative Score**: `ML_Score × SkillFactor × ExpFactor × LocFactor × SalFactor × EngFactor`

[Подробная документация](./services/search/README.md)

### 👤 Candidate Service - Управление профилями

**CRUD кандидатов** с иерархическими данными (опыт, навыки, проекты, образование).

**Ключевые паттерны**:

- **Outbox Pattern**: background worker публикует события в RabbitMQ с гарантией доставки (batch 50/2sec, max retries 5, DLQ)
- **IdempotencyMiddleware**: защита от дублирования через Idempotency-Key
- **Circuit Breaker**: graceful degradation при недоступности Employer Service
- **Контроль доступа**: видимость контактов (public/on-request/hidden) с запросами разрешения
- **File Management**: интеграция с File Service (presigned URLs)

[Подробная документация](./services/candidate/README.md)

### 📱 Bot Service - Telegram интерфейс

**Двурольный FSM-based бот** для кандидатов и работодателей.

**Кандидаты FSM**: 8 состояний для регистрации и редактирования

- Ввод базовой информации (имя, роль, локация)
- Блочный ввод (опыт, навыки, проекты, образование)
- Загрузка резюме и аватара
- FSMTimeoutMiddleware: очистка state после 30 минут неактивности

**Работодатели FSM**: 3 состояния для поиска

- Ввод фильтров поиска (роль, навыки, опыт, локация, зарплата)
- Просмотр результатов (аватар + полная информация)
- Принятие решений (лайк/контакт запрос)

[Подробная документация](./services/bot/README.md)

### 🔐 Auth Service - JWT токены

**Двусторонняя аутентификация**:

- Bot Auth: доверенный источник (INTERNAL_BOT_SECRET)
- Telegram Auth: HMAC-SHA256 верификация

**JWT Pair**:

- Access Token: 60 минут (sub/tg_id/role)
- Refresh Token: 7 дней (ротация с удалением старого)

[Подробная документация](./services/auth/README.md)

### 💼 Employer Service - Поиск и контакты

**Профили работодателей** с сессиями поиска.

**Контакт запросы workflow**:

1. Public: контакты видны сразу
2. On-request: employer отправляет запрос → candidate одобряет
3. Hidden: контакты никогда не видны

**Internal endpoint**: `/internal/access-check` для проверки разрешений (используется Candidate Service через Circuit Breaker)

[Подробная документация](./services/employer/README.md)

### 📁 File Service - Управление файлами

**S3/MinIO интеграция** для резюме и аватаров.

Ключевые функции:

- **Magic Bytes валидация**: проверка реального типа файла
- **Presigned URLs**: временные ссылки (TTL 1 час) для скачивания
- **Метаданные**: size_bytes, content_type, owner_telegram_id
- **Domain rewriting**: поддержка CDN через S3_PUBLIC_DOMAIN
- **Контроль доступа**: только владелец может удалить

[Подробная документация](./services/file/README.md)

## Технологический стек

### Backend & Framework

- **FastAPI 0.118.0** с Uvicorn + UVLoop (асинхронный I/O)
- **Python 3.12**, Pydantic 2.11+ для валидации
- **SQLAlchemy 2.0.43** ORM (PostgreSQL)

### Databases & Storage

- **PostgreSQL 15**: основная БД (async: asyncpg)
- **Elasticsearch 8.11**: лексический поиск с BM25 scoring
- **Milvus**: векторный поиск (768-dim embeddings)
- **Redis**: FSM state + token caching
- **S3/MinIO**: объектное хранилище файлов

### ML & Search

- **Sentence Transformers** `paraphrase-multilingual-mpnet-base-v2`: 768-dim embeddings
- **Cross-Encoder** `ms-marco-MiniLM-L-6-v2`: L2 переранжирование

### Message & Events

- **RabbitMQ 3.12** с aio-pika 9.5.7 (TOPIC exchange)
- **Outbox pattern**: гарантия доставки (batch worker, DLQ)

### Bot & Integration

- **aiogram 3.5.0**: Telegram bot framework
- **httpx**: async HTTP client с tenacity retry
- **python-jose + cryptography**: JWT + HMAC-SHA256

### Resilience & Monitoring

- **Circuit Breaker**: 2 states (CLOSED/OPEN), failure threshold
- **Tenacity**: exponential backoff retry logic
- **slowapi**: rate limiting (per-IP)
- **Prometheus + OpenTelemetry**: metrics + tracing
- **Structlog**: JSON structured logging

## Быстрый старт

### Docker Compose

```bash
git clone <repo>
cd it_recruiter_monorepo
cp .env.example .env

# Запустить все сервисы
docker-compose up -d

# Проверить здоровье
curl http://localhost:8000/health  # API Gateway
curl http://telegram-bot:8081/health  # Bot Service
```

### Конфигурация

Главные переменные окружения (`.env`):

```bash
# Databases
DATABASE_URL="postgresql+asyncpg://user:pass@postgres/itrecruiter"
REDIS_HOST="redis"
REDIS_PORT=6379

# Elasticsearch & Milvus
ELASTICSEARCH_URL="http://elasticsearch:9200"
MILVUS_HOST="milvus"
MILVUS_PORT=19530

# File Service (S3)
S3_ENDPOINT="http://minio:9000"
S3_ACCESS_KEY="minioadmin"
S3_SECRET_KEY="minioadmin"
S3_BUCKET="candidate-files"
S3_PUBLIC_DOMAIN="https://cdn.example.com"  # Optional CDN

# RabbitMQ
RABBITMQ_HOST="rabbitmq"
RABBITMQ_USER="guest"
RABBITMQ_PASS="guest"

# Telegram Bot
TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
INTERNAL_BOT_SECRET="your-secret-key"

# JWT
SECRET_KEY="your-secret-key-for-jwt"
ALGORITHM="HS256"

# Logging
LOG_LEVEL="INFO"
ENVIRONMENT="production"
```

### API Gateway routing

Nginx маршрутизирует на основе пути:

```nginx
/v1/auth/*          → Auth Service (8010)
/v1/candidates/*    → Candidate Service (8020)
/v1/employers/*     → Employer Service (8030)
/v1/search/*        → Search Service (8040)
/v1/files/*         → File Service (8050)
/telegram/*         → Bot Service (8081)
```

## End-to-End сценарии

### Сценарий 1: Кандидат создает профиль

```
1. /start в Telegram →  Bot Service
2. Выбирает роль "candidate" →  Starts CandidateFSM
3. Вводит данные (опыт, навыки, проекты) →  Многошаговый FSM
4. Загружает резюме →  File Service (presigned URL)
5. Creates candidate →  Candidate Service
6. Event published →  RabbitMQ (candidate.created)
7. Search Service consumer →  Индексирует в ES + Milvus
8. Готов к поиску работодателями ✅
```

### Сценарий 2: Работодатель ищет кандидата

```
1. /search в Telegram →  Bot Service
2. Вводит фильтры (роль, навыки, опыт, локация, зарплата)
3. Нажимает "Show next" →  Employer Service
4. Call /search/next →  Search Service (гибридный поиск)
   - ES (BM25) ↔ Milvus (embeddings)
   - RRF merge
   - Cross-Encoder L2 reranking
   - Multiplicative scoring
5. Returns best candidate →  с match_score и объяснением
6. Employer принимает решение (like/contact) →  Decision saved
7. Contact request if needed →  Candidate gets notified ✅
```

### Сценарий 3: Контакт запрос (On-Request контакты)

```
1. Employer хочет контакт кандидата (hidden/on-request)
2. Отправляет ContactRequest →  Employer Service
3. Candidate Service слушает через Circuit Breaker
   - Проверяет visibility (public/on-request/hidden)
   - Создает ContactsRequest в БД
4. Candidate получает уведомление в Telegram
5. Одобряет/отклоняет
6. Employer получает контакт или отказ ✅
```

## Observability

### Prometheus Метрики

Доступны на каждом сервисе (port :9090 обычно):

```
# Search Service специфичные
search_requests_total{status="success"}
search_latency_seconds{quantile="0.99"}
rrf_combined_scores{status="ok"}

# Общие для всех
http_requests_total{method="POST",endpoint="/v1/..."}
http_request_duration_seconds{quantile="0.95"}
db_pool_size{service="candidate"}
```

### OpenTelemetry Трейсинг

Настроен через OTLP exporter на port 4318 (default):

```
- Каждый /next запрос в Search Service → trace
  ├─ ES query span
  ├─ Milvus search span
  ├─ RRF computation span
  ├─ mget ES span
  └─ Cross-Encoder reranking span
```

### Structlog JSON логирование

Все компоненты пишут структурированные JSON логи:

```json
{
  "timestamp": "2026-03-09T12:31:45.123Z",
  "level": "INFO",
  "event": "candidate_indexed",
  "candidate_id": "550e8400-...",
  "es_indexed": true,
  "milvus_indexed": true,
  "service": "search",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

## Тестирование

### Unit тесты

```bash
# Все сервисы
cd services/search && pytest tests/unit/ -v --cov=app
cd services/candidate && pytest tests/unit/ -v --cov=app
cd services/bot && pytest tests/unit/ -v --cov=app
```

### E2E тесты

```bash
# Полный цикл поиска
pytest tests/e2e/test_full_search_flow.py -v
```

### Load тесты

```bash
# Locust для стресс тестирования
locust -f services/search/tests/locustfile.py \
  --host=http://localhost:8000 \
  --users=500 --spawn-rate=50 --run-time=10m
```

Целевые метрики:

- Throughput: >2000 rps
- P99 latency: <500ms
- Success rate: >99.5%

## CI/CD

GitHub Actions workflows для каждого сервиса:

```yaml
1. Unit + E2E tests (pytest)
2. Docker build (multi-stage)
3. Push to Docker Registry
4. Deploy to staging (manual)
5. Smoke tests
6. Deploy to production (manual)
```

## Масштабируемость

### Horizontal Scaling

- **Search Service**: stateless, scale за счет Elasticsearch shards
- **Candidate/Employer**: stateless, load-balanced за Nginx
- **Bot Service**: scale за счет Redis FSM хранилища
- **RabbitMQ Consumer**: parallel workers (одна очередь, разные воркеры)

### Performance Tuning

- **Elasticsearch**: tune JVM heap, add shards, enable compression
- **Milvus**: increase vector search threads, add index replicas
- **PostgreSQL**: connection pooling (pgBouncer), index optimization
- **Redis**: persistence (AOF), cluster mode для resilience

## Решение проблем

**Проблема**: Медленный поиск (P99 > 1s)

- Профилировать: ES query latency (`_explain` API)
- Масштабировать: Elasticsearch nodes
- Оптимизировать: RETRIEVAL_SIZE параметр

**Проблема**: Outbox события не доставляются

- Проверить: RabbitMQ connection (logs)
- DLQ inspection: посмотреть failed messages
- Max retries: переконфигурировать OutboxWorker

**Проблема**: Circuit Breaker открыт

- Проверить: целевой сервис доступен
- Manual reset: удалить state из кеша
- Настроить: threshold, timeout parameters

## Гарантии и соглашений

- **Outbox Pattern**: каждое событие будет доставлено (max retries, DLQ)
- **Idempotency**: повторно сделанный запрос не создаст дубли
- **Circuit Breaker**: каскадные отказы не распространяются
- **Трансакционность**: создание candidate + Outbox в одной транзакции

## Лицензия

Проприетарное ПО. Все права защищены.

## Контакты

Архитектор: Костерин Дмитрий  
Документация: Обновляется регулярно
