# Auth Service

Сервис аутентификации и управления сессиями. Выдает JWT токены при входе через Telegram и управляет их жизненным циклом (ротация, revocation).

## Описание

Обеспечивает безопасную аутентификацию и поддерживает два способа входа:

**Bot Auth** - для входа через Telegram бота (доверенный источник с secret):
- Проверка bot_secret (INTERNAL_BOT_SECRET)
- Динамическое переключение ролей (candidate/employer)
- Удаление старых сессий (max 5 активных устройств)

**Telegram Auth** - для прямой аутентификации (HMAC-SHA256 verification):
- HMAC-SHA256 проверка подлинности данных
- Проверка временного окна (max 24 часа)
- Создание/обновление пользователей

**JWT Pair Tokensами** (Access + Refresh):
- Access Token: короткоживущий (60 минут), содержит sub/tg_id/role
- Refresh Token: долгоживущий (7 дней), для ротации пары
- Refresh Token Rotation: старый удаляется при успешной ротации
- Revocation support: отозванные токены отмечаются в БД

## Технологический стек

- **Framework**: FastAPI 0.116.1, Uvicorn с UVLoop
- **Database**: PostgreSQL 15 с SQLAlchemy 2.0.43 + asyncpg
- **Authentication**: JWT (python-jose) + HMAC-SHA256
- **Migrations**: Alembic 1.16.5 (автоматические миграции)
- **Observability**: Prometheus + OpenTelemetry + Structlog

## API Endpoints

### POST `/v1/auth/login/bot`
Аутентификация через Telegram бота (доверенный источник) с динамической передачей роли.

**Request Body**:
```json
{
  "telegram_id": 123456789,
  "username": "john_doe",
  "bot_secret": "secret_string",
  "role": "candidate" // Опционально: "candidate" или "employer"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Логика**:
1. Проверка `bot_secret` (должен совпадать с `INTERNAL_BOT_SECRET`).
2. Поиск пользователя по `telegram_id` или его создание.
3. Обновление роли (позволяет одному юзеру переключаться между Кандидатом и HR).
4. Удаление старых сессий (оставляем максимум 5 активных устройств).
5. Выдача пары токенов.

### POST `/v1/auth/login/telegram`
Аутентификация через данные, полученные от Telegram.

**Request Body**:
```json
{
  "id": 123456789,
  "first_name": "John",
  "last_name": "Doe",
  "username": "john_doe",
  "photo_url": "https://...",
  "auth_date": 1709097600,
  "hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "role": "employer"
}
```

**Response**: (как в `/login/bot`)

**Логика**:
1. Проверка подлинности данных через HMAC-SHA256:
   - Вычисляется хеш сортированной строки `key=value` параметров;
   - Сравнивается с полученным `hash`.
2. Проверка временного окна (не более 24 часов).
3. Поиск или создание пользователя (с обновлением роли).
4. Выдача пары токенов.

### POST `/v1/auth/refresh`
Ротация токенов: получение новой пары токенов по валидному Refresh Token.

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response**: (как в `/login/bot`)

**Логика**:
1. Декодирование refresh токена.
2. Поиск хеша токена в БД и проверка, что он не отозван (`revoked == False`).
3. Проверка статуса пользователя (`is_active`).
4. **Refresh Token Rotation**: старый токен удаляется из БД.
5. Выдается и сохраняется новая пара токенов.

### POST `/v1/auth/logout`
Выход с текущего устройства.

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

*Удаляет конкретный токен из базы данных. Access Token перестанет действовать по истечении своего TTL.*

### POST `/v1/auth/logout/all`
Безопасный логаут со всех устройств.

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

*Находит пользователя по токену и жестко удаляет **все** его активные сессии из БД.*

### GET `/health`
Проверка здоровья сервиса.

**Response**:
```json
{
  "status": "ok"
}
```

## Database Schema

### users таблица
```
id (UUID)              - Primary key
telegram_id (BigInt)   - Уникальный ID Telegram (индекс)
username (String)      - Username из Telegram (опционально)
role (Enum)            - Роль: CANDIDATE, EMPLOYER, ADMIN
is_active (Boolean)    - Активен ли аккаунт
created_at (DateTime)  - Время создания
```

### refresh_tokens таблица
```
id (UUID)              - Primary key
user_id (UUID)         - Foreign key на users
token_hash (String)    - SHA256 хеш токена (индекс)
expires_at (DateTime)  - Время истечения
revoked (Boolean)      - Отозван ли токен
created_at (DateTime)  - Время создания
```

## JWT Token Structure

### Access Token
Используется для межсервисной авторизации.

**Payload**:
```json
{
  "sub": "user_id (uuid)",
  "tg_id": 123456789,
  "role": "candidate|employer|admin",
  "exp": 1709101200
}
```

**TTL**: `ACCESS_TOKEN_EXPIRE_MINUTES` (по умолчанию из конфига)

### Refresh Token
Используется только для получения нового Access Token. Сама строка клиенту выдается "как есть", а в БД сохраняется только ее `SHA-256` хеш.

**Payload**:
```json
{
  "sub": "user_id (uuid)",
  "type": "refresh",
  "exp": 1709705600
}
```

**TTL**: `REFRESH_TOKEN_EXPIRE_DAYS` (по умолчанию из конфига)

## Безопасность

### Telegram Hash Verification
Алгоритм HMAC-SHA256 для верификации данных от Telegram:
1. Параметры сортируются по ключам.
2. Формируется строка `key=value\nkey=value...`
3. Вычисляется HMAC: `hmac = HMAC-SHA256(secret_key, data_string)`
  где `secret_key = SHA256(bot_token)`.
4. Полученный HMAC сравнивается с переданным хешем.
5. Проверка временного окна (не более 24 часов).

### Refresh Token Хранение
- В БД сохраняется только хеш (`SHA-256`) рефреш токена. В случае утечки дампа базы, токены останутся в безопасности.
- При каждом обновлении сессии (`/refresh`) старый токен удаляется, а пользователю выдается новый. Если украденный токен попытаются использовать повторно, система это заблокирует.

### Ограничение сессий
Во избежание переполнения базы данных (DB Memory Leak) в системе реализован механизм сборки мусора: при каждом новом логине система проверяет историю пользователя и оставляет только `MAX_ACTIVE_SESSIONS` (по умолчанию 5) самых свежих сессий.

## Миграции

Использует Alembic для управления схемой БД.

```bash
# Создание новой миграции
alembic revision --autogenerate -m "описание"

# Применение миграций
alembic upgrade head

# Откат до версии
alembic downgrade -1
```

## Конфигурация

Переменные окружения (см. `app/core/config.py`):
- `DATABASE_URL` - URL PostgreSQL (формат: `postgresql+asyncpg://user:pass@host/db`)
- `SECRET_KEY` - для подписи JWT токенов
- `ALGORITHM` - алгоритм подписи (HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - TTL access токена (по умолчанию 60)
- `REFRESH_TOKEN_EXPIRE_DAYS` - TTL refresh токена (по умолчанию 7)
- `INTERNAL_BOT_SECRET` - secret для аутентификации бота
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `LOG_LEVEL` - уровень логирования

## Запуск

### Docker
```bash
docker build -t auth-service .
docker run -p 8000:8000 auth-service
```

### Локально
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Интеграция с другими сервисами

### Для Bot Service
Бот вызывает `/v1/auth/login/bot` с `telegram_id`, `username` и `bot_secret`:
```python
response = await client.post(
    f"{auth_url}/v1/auth/login/bot",
    json={
        "telegram_id": user_id,
        "username": username,
        "bot_secret": secret
    }
)
```

### Для других сервисов
Другие микросервисы получают Access Token в заголовке:
```
Authorization: Bearer {access_token}
```

Декодируют токен и проверяют:
- Валидность подписи (используя `SECRET_KEY`)
- Роль пользователя
- TTL

## Мониторинг

- **Prometheus метрики** на `/metrics`
- **OpenTelemetry** для трейсинга
- **Структурированное логирование** через structlog

## Тестирование

```bash
pytest tests/
pytest --cov=app tests/  # с покрытием кода
```

Доступные тесты:
- `test_e2e.py` - end-to-end тесты всех сценариев
- `test_unit.py` - unit тесты отдельных компонентов

## Обработка ошибок

### Аутентификация
- `401 Unauthorized` - неверные Telegram данные или expired refresh token
- `403 Forbidden` - неверный bot secret

### Валидация
- Проверка формата Telegram hash
- Проверка временного окна (24 часа для auth_date)
- Проверка активности пользователя

### Database
- Автоматический rollback при ошибке (middleware в get_db)
- Connection pooling с `pool_pre_ping=True`
