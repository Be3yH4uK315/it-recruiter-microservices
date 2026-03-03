# IT Recruiter Platform

Полнофункциональная платформа подбора кандидатов на основе современных технологий: гибридный поиск (лексический + семантический), управление профилями, Telegram бот для взаимодействия и микросервисная архитектура.

## Обзор

IT Recruiter - это масштабируемая SaaS платформа для подбора IT специалистов:

1. **Для кандидатов**: Telegram бот для роста профиля (опыт, навыки, проекты, файлы)
2. **Для работодателей**: Поиск кандидатов по гибридным фильтрам с релевантностью
3. **Для системы**: Надежная микросервисная архитектура с гарантией доставки событий

**Главная инновация**: гибридный поиск через Elasticsearch (лексический) + Milvus (семантический) с двухуровневым ранжированием.

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     Bot Layer (Telegram)                        │
│                    Точка входа для пользователей                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                    API Gateway (Nginx)                          │
│              Маршрутизация запросов к сервисам                  │
└────┬─────────────┬──────────────┬──────────────┬────────────────┘
     │             │              │              │
     ▼             ▼              ▼              ▼
┌─────────┐  ┌────────────┐  ┌──────────┐  ┌─────────┐
│  Auth   │  │ Candidate  │  │ Employer │  │  File   │
│ Service │  │  Service   │  │ Service  │  │ Service │
└─────────┘  └────────────┘  └──────────┘  └─────────┘
     │             │              │              │
     │         ┌───┴──────────────┴──────────────┘
     │         │
     ▼         ▼
 ┌────────┐ ┌───────────────────────────┐
 │  Auth  │ │  Message Broker(RabbitMQ) │
 │   DB   │ │  Outbox Events            │
 └────────┘ └───────────┬───────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │  Search Service        │
            │  + Background Worker   │
            └──────────┬─────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      ┌────────┐  ┌─────────┐  ┌──────────┐
      │Elastic │  │ Milvus  │  │Prometheus│
      │Search  │  │(Vectors)│  │Telemetry │
      └────────┘  └─────────┘  └──────────┘
```

## Микросервисы

### 🔐 Auth Service
**Управление аутентификацией и токенами**
- JWT токены (Access + Refresh)
- Аутентификация через Telegram
- Внутренняя аутентификация для бота (доверенный источник)
- [Подробная документация](./services/auth/README.md)

### 💬 Telegram Bot Service
**Взаимодействие с пользователями**
- Регистрация профилей кандидатов
- Редактирование и загрузка файлов (резюме, аватары)
- Поиск кандидатов для работодателей
- FSM управление состояниями (30-минутный timeout)
- [Подробная документация](./services/bot/README.md)

### 👤 Candidate Service
**Управление профилями кандидатов**
- CRUD операции над профилями
- Иерархические данные (опыт, навыки, проекты, образование)
- Контроль доступа к контактам (публичные/по запросу/скрытые)
- Outbox pattern для надежной публикации событий
- Background worker для обработки очереди
- Circuit Breaker для защиты от отказов Employer Service
- [Подробная документация](./services/candidate/README.md)

### 🏢 Employer Service
**Управление профилями работодателей и поиском**
- Регистрация и профили работодателей
- Сессии поиска с фильтрами
- Управление запросами доступа к контактам
- Интеграция с Search Service для получения кандидатов
- [Подробная документация](./services/employer/README.md)

### 🔍 Search Service
**Гибридный поиск кандидатов**
- Параллельный поиск в Elasticsearch (лексический) и Milvus (семантический)
- RRF (Reciprocal Rank Fusion) для объединения результатов
- L2 переранжирование с Cross-Encoder моделями
- Multiplicative scoring (ML вероятность × факторы)
- Background consumer из RabbitMQ для синхронизации индексов
- [Подробная документация](./services/search/README.md)

### 📁 File Service
**Управление файлами**
- Загрузка резюме и аватаров в S3/MinIO
- Presigned URL для скачивания без публичного доступа
- Метаданные и контроль доступа в PostgreSQL
- [Подробная документация](./services/file/README.md)

## Сценарии использования

### 📋 Регистрация кандидата

```
1. Кандидат пишет боту /start
2. Бот ведет через FSM:
   - Ввод базовой информации
   - Добавление опыта (экспоненты, задачи)
   - Добавление навыков (с уровнями)
   - Загрузку аватара
   - Загрузку резюме
3. Профиль сохраняется в Candidate Service PostgreSQL
4. Событие `candidate.created` публикуется в RabbitMQ
5. Search Service получает событие и:
   - Индексирует профиль в Elasticsearch
   - Генерирует embedding и добавляет в Milvus
```

### 🔎 Поиск кандидатов работодателем

```
1. Работодатель пишет боту /search
2. Бот собирает фильтры (роль, навыки, опыт и т.д.)
3. Создается SearchSession в Employer Service
4. Работодатель нажимает "Следующий кандидат"
5. Employer Service вызывает Search Service /search/next
6. Search Service:
   - Паралельно ищет в ES (лексический) и Milvus (семантический)
   - Объединяет результаты методом RRF
   - Получает полный профиль из Candidate Service
   - Переранжирует с Cross-Encoder + факторами
7. Возвращает candidata с match_score
8. Бот отображает профиль работодателю
```

### 💬 Запрос доступа к контактам

```
1. Работодатель видит профиль кандидата (контакты скрыты)
2. Нажимает кнопку "Запросить контакты"
3. Employer Service создает ContactsRequest
4. Кандидат получает уведомление в боте
5. Может одобрить или отклонить
6. ContactsRequest обновляется (granted = true/false)
7. Работодателю вернулись контакты (если одобрено)
```

## Технологический стек

### Core
- **Python 3.12** - язык программирования
- **FastAPI 0.116** - веб-фреймворк для микросервисов
- **Uvicorn + UVLoop** - высокопроизводительный ASGI сервер
- **Pydantic 2.11** - валидация данных

### Databases
- **PostgreSQL 15** - основная БД (Auth, Candidate, Employer, File)
- **SQLAlchemy 2.0** + **asyncpg** - асинхронный ORM
- **Alembic** - миграции схемы
- **Redis** - FSM хранилище для бота + кеширование

### Search & ML
- **Elasticsearch 8.11** - лексический полнотекстовый поиск
- **Milvus** - векторная БД для embedding поиска
- **Sentence Transformers** - генерация embedding (paraphrase-multilingual-mpnet-base-v2)
- **Cross-Encoder** - переранжирование (ms-marco-MiniLM-L-6-v2)

### Message Broker & Events
- **RabbitMQ** - асинхронная публикация событий
- **aio-pika** - асинхронный Python клиент для RabbitMQ

### Storage
- **S3/MinIO** - объектное хранилище файлов
- **aioboto3** - асинхронный AWS S3 клиент

### Bot & HTTP
- **aiogram 3.5** - Telegram bot framework
- **httpx** - асинхронный HTTP клиент
- **tenacity** - retry логика

### Security
- **python-jose** - JWT создание и верификация
- **cryptography** - криптографические операции

### Observability
- **Prometheus** - метрики
- **OpenTelemetry** - распределенный трейсинг
- **Structlog** - структурированное логирование

### Infrastructure
- **Docker & Docker Compose** - контейнеризация
- **Nginx** - API Gateway и reverse proxy

## Запуск локально

### Требования
- Docker & Docker Compose
- Python 3.12 (для локальной разработки без Docker)
- 4+ GB RAM, 10+ GB свободного места

### Быстрый старт

```bash
# 1. Клонируем репозиторий
git clone <repository> it_recruiter
cd it_recruiter

# 2. Копируем и настраиваем переменные окружения
cp .env.example .env
# Отредактируйте .env (особенно SECRET_KEY, BOT_TOKEN и S3 параметры)

# 3. Запускаем все сервисы через Docker Compose
docker-compose up -d

# 4. Проверяем здоровье сервисов
curl http://localhost:8001/health  # Auth
curl http://localhost:8002/health  # Candidate
curl http://localhost:8003/health  # Employer
curl http://localhost:8004/health  # File
curl http://localhost:8005/health  # Search
curl http://localhost/health       # Gateway
```

### Запуск отдельного сервиса локально

```bash
cd services/auth
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Выполняем миграции
alembic upgrade head

# Запускаем сервис
uvicorn app.main:app --reload
```

## Конфигурация

Все сервисы читают переменные из `.env` файла:

```bash
# Security
SECRET_KEY=<генерируется>
INTERNAL_BOT_SECRET=<генерируется>
BOT_TOKEN=<из @BotFather>

# Databases & RabbitMQ
AUTH_DATABASE_URL=postgresql+asyncpg://...
CANDIDATE_DATABASE_URL=postgresql+asyncpg://...
EMPLOYER_DATABASE_URL=postgresql+asyncpg://...
FILE_DATABASE_URL=postgresql+asyncpg://...
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672

# S3/MinIO
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=recruiter-files
S3_PUBLIC_DOMAIN=https://your-domain.com

# Search
ELASTICSEARCH_URL=http://elasticsearch:9200
MILVUS_HOST=milvus
MILVUS_PORT=19530

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Logs & Monitoring
LOG_LEVEL=INFO
ENVIRONMENT=local
```

## API Gateway

Nginx Gateway маршрутизирует запросы:
```
GET  /health                  → Gateway
POST /v1/auth/*              → Auth Service
POST /v1/candidates/*        → Candidate Service
POST /v1/employers/*         → Employer Service
POST /v1/search/*            → Search Service
POST /v1/files/*             → File Service
```

## Мониторинг

### Prometheus
```bash
curl http://localhost:9090

# Метрики доступны на каждом сервисе:
http://localhost:8001/metrics  # Auth
http://localhost:8002/metrics  # Candidate
...
```

### OpenTelemetry
Распределенный трейсинг через OTLP exporter. Сконфигурировано для отправки в Jaeger (если запущен).

### Логирование
Structlog выводит JSON логи с контекстом:
```json
{
  "timestamp": "2026-02-28T10:30:00.000Z",
  "level": "INFO",
  "logger": "app.services.candidate",
  "message": "Candidate indexed",
  "candidate_id": "550e8400-e29b-41d4-a716-446655440000",
  "telegram_id": 123456789
}
```

## Тестирование

Каждый сервис содежит набор тестов:

```bash
# Unit тесты
pytest tests/unit/

# E2E тесты
pytest tests/test_e2e.py

# Integration тесты
pytest tests/test_integration.py

# С покрытием кода
pytest --cov=app tests/

# Load тесты (Locust)
locust -f tests/locustfile.py --host=http://localhost
```

## Развертывание

### Production Deployment

1. **Генерируем секреты**:
   ```bash
   openssl rand -hex 32  # SECRET_KEY
   openssl rand -hex 32  # INTERNAL_BOT_SECRET
   ```

2. **Настраиваем переменные окружения**:
   - Реальные URLs для всех сервисов
   - S3 credentials или использование S3 AWS
   - Database credentials с мощными паролями

3. **Выполняем миграции**:
   ```bash
   docker-compose exec auth-api alembic upgrade head
   docker-compose exec candidate-api alembic upgrade head
   docker-compose exec employer-api alembic upgrade head
   docker-compose exec file-api alembic upgrade head
   ```

4. **Масштабируем сервисы**:
   ```bash
   docker-compose up -d --scale search-consumer=3
   docker-compose up -d --scale candidate-worker=2
   ```

## Структура репозитория

```
it_recruiter/
├── README.md                 # Этот файл
├── docker-compose.yml        # Конфигурация всех сервисов
├── .env.example              # Шаблон переменных окружения
│
├── services/
│   ├── auth/                 # Сервис аутентификации
│   ├── bot/                  # Telegram бот
│   ├── candidate/            # Управление профилями кандидатов
│   ├── employer/             # Управление работодателями и поиском
│   ├── file/                 # Управление файлами
│   └── search/               # Гибридный поиск с ML
│
└── infrastructure/
    ├── nginx/                # API Gateway конфигурация
    └── prometheus/           # Мониторинг конфигурация
```

## Health Checks

Каждый сервис имеет `/health` эндпоинт:

```bash
# Проверка всех сервисов одной командой
for port in 8001 8002 8003 8004 8005; do
  echo "Port $port:"; curl -s http://localhost:$port/health | jq .
done

# Или через Gateway
curl http://localhost/health
```

## Документация сервисов

- [Auth Service](./services/auth/README.md) - JWT аутентификация
- [Bot Service](./services/bot/README.md) - Telegram взаимодействие
- [Candidate Service](./services/candidate/README.md) - Профили кандидатов
- [Employer Service](./services/employer/README.md) - Поиск и управление
- [File Service](./services/file/README.md) - Управление файлами
- [Search Service](./services/search/README.md) - Гибридный поиск

## Основные компоненты

### Resilience Patterns

1. **Circuit Breaker** - защита от каскадных отказов
   - Candidate Service → Employer Service
   - Employer Service → Search Service

2. **Retry with Exponential Backoff** - через tenacity
   - HTTP запросы между сервисами
   - S3 операции
   - RabbitMQ вторичные события

3. **Idempotency** - защита от дублирования при повторах
   - Middleware в Candidate Service
   - Обработка через Idempotency-Key заголовок

4. **Outbox Pattern** - гарантия доставки событий
   - События записываются в таблицу перед публикацией
   - Background worker публикует с retry логикой
   - На отказ - отправка в DLQ

### Data Consistency

- **Транзакции в PostgreSQL** - atomicity на уровне БД
- **Event Sourcing элементы** - через Outbox таблицу
- **Оптимистичные блокировки** - через версионирование где нужно

### Scalability

- **Асинхронная архитектура** - async/await везде
- **Connection pooling** - для БД и HTTP
- **Message queue** - для отязки сервисов
- **Кеширование** - Redis для токенов, Elasticsearch/Milvus для поиска
- **Stateless сервисы** - можно масштабировать горизонтально

## Производительность

### Типичные метрики

| Операция | Время |
|----------|-------|
| Поиск кандидата | < 500ms |
| Загрузка файла (10MB) | < 2s |
| Создание профиля | < 1s |
| Индексирование в Search | < 100ms |

### Оптимизации

- UVLoop вместо стандартного event loop
- Асинхронная БД через asyncpg
- Connection pooling с pre-ping
- Потоковая загрузка файлов в S3
- Кеширование embeddings моделей в памяти

## Лицензия

Проприетарное ПО. Все права защищены.

## Контакты

Архитектор: Костерин Дмитрий  
Документация: Обновляется регулярно
