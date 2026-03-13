# Employer Service

Микросервис управления профилями работодателей, сессиями поиска и аналитикой найма. Организует поиск через Search Service и управляет запросами доступа к контактам кандидатов.

## Описание

Основная функциональность:
- **Профили работодателей**: регистрация и обновление компаний
- **Сессии поиска**: создание сессий с фильтрами (роль, навыки, опыт, локация, зарплата)
- **Поиск кандидатов**: интеграция с Search Service (получение лучшего кандидата на основе RRF + L2 ранжирования)
- **Воронка найма**: принятие решений (like/dislike) и ведение HR-аналитики
- **Контакт запросы**: трехуровневая схема доступа (public/on-request/hidden)
- **Проверка доступа**: валидация разрешений для Candidate Service (internal endpoint)
- **Circuit Breaker**: защита от отказов Candidate и Search сервисов

## Технологический стек

- **Framework**: FastAPI 0.116.1, Uvicorn с UVLoop
- **Database**: PostgreSQL 15 (SQLAlchemy 2.0.43 + asyncpg)
- **Resilience**: Circuit Breaker (2 states) + Tenacity retry
- **Observability**: Prometheus + OpenTelemetry + Structlog

## API Endpoints

### POST `/v1/`
Регистрация/получение профиля работодателя.

**Request Body**:
```json
{
  "telegram_id": 987654321,
  "company": "TechCorp",
  "contacts": {
    "email": "hr@techcorp.com",
    "phone": "+7-999-999-99-99"
  }
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "telegram_id": 987654321,
  "company": "TechCorp",
  "contacts": {
    "email": "hr@techcorp.com",
    "phone": "+7-999-999-99-99"
  }
}
```

**Логика**: Если работодатель уже зарегистрирован (по telegram_id) - возвращает существующий профиль, иначе создает новый.

### PATCH `/v1/{employer_id}`
Обновление профиля работодателя.

**Request Body**:
```json
{
  "company": "NewCompanyName",
  "contacts": {"email": "newemail@company.com"}
}
```

**Response**: обновленный профиль

### POST `/v1/{employer_id}/searches`
Создание новой сессии поиска кандидатов.

**Request Body**:
```json
{
  "title": "Поиск Senior Python Developer",
  "filters": {
    "role": "Python Developer",
    "must_skills": [
      {"skill": "python", "level": 5},
      {"skill": "fastapi", "level": 4}
    ],
    "nice_skills": [
      {"skill": "docker", "level": 3}
    ],
    "experience_min": 3,
    "experience_max": 20,
    "location": "Moscow",
    "work_modes": ["remote", "hybrid"],
    "salary_max": 500000,
    "currency": "RUB",
    "english_level": "B2"
  }
}
```

**Response**:
```json
{
  "id": "uuid",
  "employer_id": "uuid",
  "title": "Поиск Senior Python Developer",
  "filters": {...},
  "status": "active",
  "created_at": "2026-02-28T10:30:00Z",
  "updated_at": "2026-02-28T10:30:00Z"
}
```

### POST `/v1/searches/{session_id}/next`
Получение следующего кандидата для сессии поиска.

**Response**:
```json
{
  "candidate": {
    "id": "uuid",
    "display_name": "Иван Петров",
    "headline_role": "Senior Python Developer",
    "experience_years": 5.5,
    "location": "Moscow",
    "work_modes": ["remote"],
    "skills": ["Python (5/5)", "FastAPI (3/5)", "PostgreSQL (4/5)"],
    "salary_min": 200000,
    "salary_max": 400000,
    "english_level": "B2",
    "match_score": 0.92,
    "explanation": {
      "ml_score": 0.88,
      "skill_factor": 1.0,
      "exp_factor": 0.95
    },
    "contacts": null,
    "contacts_visibility": "on_request",
    "avatars": [],
    "resumes": [...]
  }
}
```

**Логика**:
1. Получает просмотренные ID из текущей сессии.
2. Вызывает Search Service с фильтрами и исключенными ID.
3. Получает полный профиль кандидата из Candidate Service.
4. Возвращает кандидата с оценкой релевантности (match_score) с контактами скрытыми по умолчанию.

**Возможные ответы**:
- Кандидат найден - возвращает полный профиль.
- Кандидаты закончились - возвращает сообщение "No more candidates found".
- Search Service недоступен - возвращает 503.

### POST `/v1/searches/{session_id}/decisions`
Отправка решения по кандидату (like, dislike, skip).

**Request Body**:
```json
{
  "candidate_id": "uuid",
  "decision": "like",
  "note": "Отличный кандидат, соответствует всем требованиям"
}
```

**Response**:
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "candidate_id": "uuid",
  "decision": "like",
  "note": "Отличный кандидат, соответствует всем требованиям"
}
```

**Decision Types**: `like`, `dislike`, `skip`

**Уникальность**: Одна сессия может иметь только одно решение для каждого кандидата.

### GET `/v1/employers/{employer_id}/favorites`
Получить всех кандидатов, которых HR сохранил в закладки (решение LIKE по всем его сессиям). Запрашивает профили параллельно из Candidate Service.

### GET `/v1/employers/{employer_id}/unlocked-contacts`
Получить всех кандидатов, которые разрешили данному HR доступ к своим контактам.

### GET `/v1/employers/{employer_id}/searches`
Получить историю сессий поиска данного HR.

### GET `/v1/employers/{employer_id}/statistics`
Получить агрегированную воронку рекрутмента HR'а.

**Response**:
```json
{
  "total_viewed": 150,
  "total_liked": 15,
  "total_contact_requests": 10,
  "total_contacts_granted": 3
}
```

### GET `/v1/employers/candidates/{candidate_id}/statistics`
Внутренний эндпоинт для Candidate Service. Возвращает эго-метрику кандидата.

**Response**:
```json
{
  "total_views": 42,
  "total_likes": 5,
  "total_contact_requests": 2
}
```

### POST `/v1/{employer_id}/contact-requests`
Запрос доступа к контактам кандидата.

**Request Body**:
```json
{
  "candidate_id": "uuid"
}
```

**Response**:
```json
{
  "granted": false,
  "notification_info": {
    "candidate_telegram_id": 123456789,
    "employer_company": "TechCorp",
    "request_id": "uuid"
  }
}
```

или при публичных контактах:

```json
{
  "granted": true,
  "contacts": {
    "email": "candidate@example.com",
    "phone": "+7-999-123-45-67"
  }
}
```

**Логика**:
1. Проверяет видимость контактов кандидата:
   - `public` - контакты выдаются сразу
   - `on_request` - создает запрос, отправляет уведомление кандидату
   - `hidden` - доступ всегда запрещен
2. Если контакты уже были разрешены ранее - возвращает сохраненный ответ
3. Отправляет уведомление кандидату с информацией о работодателе и ID запроса

### PUT `/v1/contact-requests/{request_id}`
Ответ кандидата на запрос доступа к контактам.

**Request Body**:
```json
{
  "granted": true
}
```

**Response**:
```json
{
  "status": "updated"
}
```

### GET `/v1/contact-requests/{request_id}/details`
Получение информации о запросе (для кандидата).

**Response**:
```json
{
  "id": "uuid",
  "employer_telegram_id": 987654321,
  "candidate_name": "Иван Петров",
  "candidate_id": "uuid"
}
```

### GET `/v1/internal/access-check`
Проверка прав доступа работодателя к контактам кандидата (внутренний эндпоинт).

**Query Parameters**:
- `candidate_id` (UUID)
- `employer_telegram_id` (int)

**Response** (если доступ разрешен):
```json
{
  "granted": true
}
```

**Response** (если доступ запрещен): 403 Forbidden

**Использование**: Candidate Service вызывает этот эндпоинт при возвращении профиля, чтобы решить скрывать ли контакты.

### GET `/health`
Проверка здоровья сервиса.

**Response**:
```json
{
  "status": "ok"
}
```

## Database Schema

### employers таблица
```
id (UUID) - Primary key
telegram_id (BigInt) - Уникальный (индекс)
company (String) - Название компании (опционально)
contacts (JSONB) - Резервная копия контактов
created_at (DateTime)
updated_at (DateTime)
```

### search_sessions таблица
```
id (UUID) - Primary key
employer_id (UUID) - Foreign key на employers (cascade delete)
title (String) - Название поиска
filters (JSONB) - Фильтры поиска (роль, навыки, опыт и т.д.)
status (Enum) - active, paused, closed
created_at (DateTime)
updated_at (DateTime)
```

### decisions таблица
```
id (UUID) - Primary key
session_id (UUID) - Foreign key на search_sessions (cascade delete)
candidate_id (UUID) - ID кандидата из Candidate Service
decision (Enum) - like, dislike, skip
note (String) - Заметка работодателя
created_at (DateTime)

Уникальный индекс: (session_id, candidate_id)
```

### contacts_requests таблица
```
id (UUID) - Primary key
employer_id (UUID) - Foreign key на employers
candidate_id (UUID) - ID кандидата из Candidate Service (индекс)
granted (Boolean) - Одобрен ли запрос
created_at (DateTime)
```

## Управление контактами: Workflow

### Сценарий 1: Публичные контакты
```
Работодатель запрашивает контакты кандидата
  ↓
Проверка видимости (contacts_visibility = "public")
  ↓
Контакты выдаются сразу
```

### Сценарий 2: Контакты по запросу
```
Работодатель запрашивает контакты кандидата
  ↓
Проверка видимости (contacts_visibility = "on_request")
  ↓
Создается запись в contacts_requests (granted = false)
  ↓
Отправляется уведомление кандидату в Telegram Bot
  ↓
Кандидат одобряет/отклоняет
  ↓
contacts_requests.granted = true/false
  ↓
Работодатель получает контакты (если одобрено)
```

### Сценарий 3: Скрытые контакты
```
Работодатель запрашивает контакты кандидата
  ↓
Проверка видимости (contacts_visibility = "hidden")
  ↓
Доступ запрещен
```

## Circuit Breaker

**SimpleCircuitBreaker** для защиты от отказов сервисов:
- **Состояния**: CLOSED (работает), OPEN (не работает), HALF-OPEN (проверка)
- **Threshold**: N ошибок открывают circuit
- **Recovery Timeout**: время для переходы в HALF-OPEN
- **Использование**: при запросах к Candidate Service и Search Service

## Поиск кандидатов: Flow

1. Работодатель создает сессию поиска с фильтрами
2. Вызывает `/next` для получения кандидатов
3. Сервис отправляет фильтры в Search Service
4. Search Service возвращает ID лучшего кандидата с оценкой
5. Сервис получает полный профиль из Candidate Service
6. Возвращает кандидата работодателю
7. Работодатель может:
   - Поставить like/dislike/skip
   - Запросить контакты (если нужно)
   - Запросить следующего кандидата

## Конфигурация

Переменные окружения (см. `app/core/config.py`):
- `DATABASE_URL` - PostgreSQL (формат: `postgresql+asyncpg://user:pass@host/db`)
- `CANDIDATE_SERVICE_URL` - URL Candidate Service
- `SEARCH_SERVICE_URL` - URL Search Service
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` - количество ошибок для открытия circuit
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` - время восстановления (сек)
- `RATE_LIMIT_DEFAULT` - лимит запросов
- `SECRET_KEY`, `ALGORITHM` - для подписи токенов

## Запуск

### Docker
```bash
docker build -t employer-service .
docker run -p 8000:8000 employer-service
```

### Локально
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
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
- `test_e2e.py` - end-to-end тесты полного цикла
- `test_integration.py` - интеграционные тесты с внешними сервисами
- `test_circuit_breaker.py` - тесты Circuit Breaker логики
- `test_service_edge_cases.py` - edge case тесты
- `test_unit.py` - unit тесты отдельных компонентов

## Мониторинг

- **Prometheus метрики** на `/metrics`
- **OpenTelemetry** для трейсинга распределенных операций
- **Structlog** для структурированного логирования

## Обработка ошибок

### Валидация
- Проверка формата UUID для ID
- Валидация SearchStatus и DecisionType enum значений
- Проверка минимальной длины названия сессии (3 символа)

### Resilience
- **Circuit Breaker**: автоматическое отключение при сбойных сервисах
- **HTTP Errors**: 
  - 404 - сессия не найдена
  - 503 - Search Service недоступен
  - 403 - доступ к контактам запрещен

### Database
- Автоматический rollback при ошибке
- Connection pooling с правильной конфигурацией
- Cascade delete для связанных данных (сессии и решения удаляются с работодателем)

## Интеграция с другими сервисами

### Search Service
- `POST /v1/search/next` - получение следующего кандидата по фильтрам
- Отправляет:
  - `session_id` - для отслеживания
  - `filters` - критерии поиска
  - `session_exclude_ids` - просмотренные кандидаты в этой сессии

### Candidate Service
- `GET /candidates/{id}` - получение полного профиля кандидата
- `GET /candidates/by-telegram/{telegram_id}` - поиск по Telegram ID
- `GET /internal/access-check` - проверка доступа к контактам (вызывается Candidate Service)

## Особенности

### Сессии поиска
- Независимые друг от друга - разные сессии могут иметь разные фильтры
- Отслеживают просмотренных кандидатов - не показывают одних и тех же дважды в одной сессии
- Изолируют решения - глобальные решения не влияют на других работодателей

### Управление доступом
- Полностью контролируется кандидатом через `contacts_visibility`
- Работодателю предоставляется уведомление с информацией для контакта
- Кандидат видит кто и когда запрашивал его контакты
- Разовое одобрение - повторные запросы того же работодателя выдают контакты сразу

### Performance
- Использует Circuit Breaker для защиты от косвенных отказов
- Кеширует просмотренные ID в памяти сессии
- Кеширует информацию о контактах в requests таблице
