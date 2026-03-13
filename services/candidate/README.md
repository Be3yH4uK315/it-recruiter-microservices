# Candidate Service

Микросервис управления профилями кандидатов. Сохраняет данные, управляет файлами, публикует события для синхронизации индексов и контролирует доступ к контактам.

## Описание

Основная функциональность:
- **CRUD профилей**: создание, чтение, обновление кандидатов с иерархическими данными
- **Иерархические data**: опыт работы, навыки (уровни 1-5), проекты, образование, резюме, аватары
- **Outbox Pattern**: надежная публикация событий в RabbitMQ через background worker (batch processing 50 msgs/2sec)
- **Идемпотентность**: защита от дублей через Idempotency-Key header (middleware-level)
- **Circuit Breaker**: graceful degradation при недоступности Employer Service (2-state: CLOSED/OPEN)
- **Контроль доступа**: видимость контактов (public/on-request/hidden) с проверкой разрешений
- **File Management**: интеграция с File Service для presigned URLs и удаления

## Технологический стек

- **Framework**: FastAPI 0.116.1, Uvicorn с UVLoop
- **Database**: PostgreSQL 15 с SQLAlchemy 2.0.43 + asyncpg
- **Message Broker**: RabbitMQ (aio-pika 9.5.7, TOPIC exchange)
- **Resilience**: Circuit Breaker + Tenacity + Outbox + Idempotency middleware
- **Observability**: Prometheus + OpenTelemetry + Structlog

## API Endpoints

### POST `/v1/candidates`
Создание профиля кандидата.

**Request Body**:
```json
{
  "telegram_id": 123456789,
  "display_name": "Иван Иванов",
  "headline_role": "Python Developer",
  "location": "Moscow",
  "work_modes": ["remote", "hybrid"],
  "experiences": [
    {
      "company": "Яндекс",
      "position": "Senior Engineer",
      "start_date": "2020-01-15",
      "end_date": null,
      "responsibilities": "Разработка API"
    }
  ],
  "skills": [
    {
      "skill": "python",
      "kind": "language",
      "level": 5
    }
  ],
  "projects": [],
  "education": [
    {
      "level": "Бакалавр",
      "institution": "МГУ",
      "year": 2020
    }
  ],
  "english_level": "B2",
  "about_me": "Опытный разработчик",
  "contacts": {
    "phone": "+7-999-123-45-67",
    "email": "ivan@example.com"
  },
  "contacts_visibility": "public"
}
```

**Response** (201 Created): согласно схеме `Candidate`

### GET `/v1/candidates`
Получение списка кандидатов (для администраторов).

**Query Parameters**:
- `offset` (int, default=0)
- `limit` (int, default=20, max=100)

**Response**:
```json
{
  "total": 150,
  "limit": 20,
  "offset": 0,
  "data": [...]
}
```

### GET `/v1/candidates/{candidate_id}`
Получение профиля по ID.

**Response**: согласно схеме `Candidate` (контакты скрываются автоматически в зависимости от прав viewer_id).

### GET `/v1/candidates/by-telegram/{telegram_id}`
Получение профиля по Telegram ID.

**Response**: согласно схеме `Candidate`

### PATCH `/v1/candidates/by-telegram/{telegram_id}`
Обновление профиля (требует проверки владельца).

**Request Body**: согласно схеме `CandidateUpdate`

**Response**: обновленный профиль

**Побочный эффект**: отправка события candidate.updated.profile в Outbox для Search Service.

### GET `/v1/candidates/by-telegram/{telegram_id}/statistics`
Получение статистики кандидата (агрегация из Employer Service).

**Response**:
```json
{
  "total_views": 42,
  "total_likes": 5,
  "total_contact_requests": 2
}
```

### PUT `/v1/candidates/by-telegram/{telegram_id}/avatar`
Установка аватара кандидата. Старый файл синхронно удаляется из File Service.

**Request Body**:
```json
{
  "file_id": "uuid-of-uploaded-file"
}
```

**Response**:
```json
{
  "id": "uuid",
  "candidate_id": "uuid",
  "file_id": "uuid",
  "created_at": "2026-02-28T10:30:00Z"
}
```

### DELETE `/v1/candidates/by-telegram/{telegram_id}/avatar`
Удаление аватара (через Outbox).

**Response**: 204 No Content

### POST `/v1/candidates/by-telegram/{telegram_id}/resume/upload-url`
Получение Presigned URL для загрузки резюме.

**Query Parameters**:
- `filename` (str) - имя файла
- `content_type` (str, default="application/pdf") - MIME тип

**Response**:
```json
{
  "upload_url": "https://file-service.../upload?...",
  "object_key": "resumes/123456789/resume.pdf",
  "expires_in": 3600
}
```

### PUT `/v1/candidates/by-telegram/{telegram_id}/resume`
Привязка загруженного файла к профилю.

**Request Body**:
```json
{
  "file_id": "uuid-of-uploaded-file"
}
```

**Response**: объект Resume

### DELETE `/v1/candidates/by-telegram/{telegram_id}/resume`
Удаление резюме из профиля.

**Response**: 204 No Content

### GET `/health`
Проверка здоровья сервиса (DB + RabbitMQ).

**Response**:
```json
{
  "status": "ok",
  "components": {
    "db": "up",
    "rabbitmq": "up"
  }
}
```

## Database Schema

### candidates таблица
Основная таблица профилей кандидатов со всеми базовыми данными.

```
id (UUID) - Primary key
telegram_id (BigInt) - Уникальный (индекс)
display_name (String)
headline_role (String)
location (String)
work_modes (JSONB[])
experience_years (Float)
english_level (Enum: A1-C2)
about_me (String)
contacts (JSONB) - опционально
contacts_visibility (Enum: on_request, public, hidden)
status (Enum: active, hidden, blocked)
created_at (DateTime)
updated_at (DateTime)
```

### Связанные таблицы (с каскадным удалением)
- `candidate_experiences` - опыт работы
- `candidate_skills` - навыки с уровнями
- `candidate_projects` - проекты
- `candidate_education` - образование
- `candidate_avatars` - аватары
- `candidate_resumes` - резюме

### outbox_messages таблица
Для Outbox pattern (надежная публикация событий).

```
id (UUID) - Primary key
routing_key (String) - ключ маршрутизации RabbitMQ
message_body (JSONB)
status (String, индекс) - pending, sent, failed
retry_count (Integer) - количество попыток
error_log (String) - последняя ошибка
created_at (DateTime)
processed_at (DateTime)
```

### idempotency_keys таблица
Для защиты от дублирования при повторных запросах.

```
key (String) - Primary key (из заголовка Idempotency-Key)
response_body (JSONB) - сохраненный ответ
status_code (Integer)
created_at (DateTime)
```

## Event Publishing

### Outbox Pattern
1. При обновлении кандидата событие записывается в таблицу `outbox_messages` (в той же транзакции).
2. Отдельный Background Worker периодически читает pending сообщения через `SELECT ... FOR UPDATE SKIP LOCKED`.
3. Публикует их в RabbitMQ с гарантией доставки.
4. При успехе - отмечает как `sent`.
5. При критическом сбое после `MAX_RETRIES` гарантированно переводит в статус `failed` и отправляет в DLQ (Dead Letter Queue).

### События
| Event | Routing Key | Слушатель |
|-------|------------|-----------|
| Кандидат обновлен | `candidate.updated.profile` | Search Service (переиндексация) |
| Файл удален | `file.delete` | File Service (очистка хранилища) |

## Идемпотентность

Поддерживается через **IdempotencyMiddleware**:
- Проверяет заголовок `Idempotency-Key` в request
- Если ключ найден в БД - возвращает сохраненный ответ
- Иначе - выполняет операцию и сохраняет результат
- Работает для POST, PUT, PATCH, DELETE запросов

**Пример**:
```bash
curl -X POST /v1/candidates \
  -H "Idempotency-Key: unique-key-123" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## Circuit Breaker

**SimpleCircuitBreaker** для защиты от отказов Employer Service:
- **Состояния**: CLOSED (работает), OPEN (не работает), HALF-OPEN (проверка восстановления)
- **Threshold**: N ошибок открывают circuit
- **Recovery Timeout**: время для переходы в HALF-OPEN
- **Использование**: при проверке доступа работодателя к контактам кандидата

## Контроль доступа (Sanitization)

При получении профиля контакты могут быть скрыты в зависимости от настроек:

| Visibility | Владелец | Работодатель | Аноним |
|-----------|----------|-------------|--------|
| `PUBLIC` | ✓ | ✓ | ✓ |
| `ON_REQUEST` | ✓ | ✓ (по запросу) | ✗ |
| `HIDDEN` | ✓ | ✗ | ✗ |

Проверка доступа работодателя идет в Employer Service через Circuit Breaker.

## Background Worker

Отдельный процесс (`app/worker.py`) для обработки Outbox:
- Запускается отдельно от HTTP сервера
- Читает `outbox_messages` с `status='pending'` каждые 2 секунды
- Публикует в RabbitMQ с retry логикой
- Отправляет в DLQ при критических сбоях
- **Max retries**: 5

```bash
# В docker-compose.yml
services:
  candidate-worker:
    image: candidate-service
    command: python app/worker.py
    depends_on:
      - postgres
      - rabbitmq
```

## Rate Limiting

Настраивается через `RATE_LIMIT_DEFAULT` (по умолчанию в конфиге):
```
"100/minute"  # Пример
```

Использует slowapi middleware. Превышение возвращает 429 Too Many Requests.

## Конфигурация

Переменные окружения (см. `app/core/config.py`):
- `DATABASE_URL` - PostgreSQL (формат: `postgresql+asyncpg://user:pass@host/db`)
- `RABBITMQ_HOST`, `RABBITMQ_PORT` - параметры RabbitMQ
- `RABBITMQ_USER`, `RABBITMQ_PASS` - учетные данные
- `CANDIDATE_EXCHANGE_NAME` - имя exchange для публикации
- `DLQ_EXCHANGE_NAME` - имя exchange для DLQ
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` - количество ошибок для открытия circuit
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` - время восстановления (сек)
- `RATE_LIMIT_DEFAULT` - лимит запросов (по умолчанию)
- `FILE_SERVICE_URL` - URL File Service для получения presigned URL
- `EMPLOYER_SERVICE_URL` - URL Employer Service для проверки доступа
- `SECRET_KEY`, `ALGORITHM` - для подписи технических токенов

## Запуск

### Docker (HTTP сервер)
```bash
docker build -t candidate-service .
docker run -p 8000:8000 candidate-service
```

### Docker (Background Worker)
```bash
docker run candidate-service python app/worker.py
```

### Локально
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
# В отдельном терминале - worker
python app/worker.py
```

## Миграции

Alembic для управления схемой БД:
```bash
alembic revision --autogenerate -m "описание"
alembic upgrade head
alembic downgrade -1
```

## Тестирование

```bash
pytest tests/
pytest --cov=app tests/
```

Доступные тесты:
- `test_e2e_api.py` - end-to-end API тесты
- `test_integration_external.py` - интеграционные тесты с внешними сервисами
- `unit/test_logic.py` - unit тесты бизнес логики
- `unit/test_publisher.py` - тесты публикации событий
- `unit/test_service.py` - тесты сервиса
- `unit/test_worker.py` - тесты background worker

## Мониторинг

- **Prometheus метрики** на `/metrics`
- **OpenTelemetry** для трейсинга распределенных операций
- **Structlog** для структурированного логирования

## Обработка ошибок

### Валидация
- Проверка длины строк.
- Валидация дат (формат ГГГГ-ММ-ДД).
- Диапазоны уровней навыков (1-5).
- Проверка уникальности telegram_id.

### Resilience
- **Retry**: tenacity с exponential backoff для HTTP запросов.
- **Circuit Breaker**: автоматическое отключение при сбойных сервисах.
- **Idempotency**: защита от дублирования при сетевых ошибках.

### Database
- Автоматический rollback при ошибке.
- Connection pooling с `pool_pre_ping=True`.
- Cascade delete для связанных данных.

## Интеграция с другими сервисами

### File Service
- Получение presigned URL для загрузки.
- Удаление файлов через Outbox события.

### Employer Service (Circuit Breaker)
- Проверка доступа работодателя к контактам (`GET /internal/access-check`).
- Получение статистики кандидата (`GET /candidates/{candidate_id}/statistics`).

### Search Service
- Подписывается на события `candidate.updated.profile`.
- Переиндексирует кандидата в Milvus и Elasticsearch.
