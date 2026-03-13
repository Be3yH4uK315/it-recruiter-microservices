# Search Service

Микросервис поиска и подбора кандидатов на основе гибридного поиска (лексический + семантический). Основной компонент платформы IT recruiter для интеллектуального подбора подходящих кандидатов.

## Описание

Сервис реализует спектр возможностей для поиска кандидатов:

- **Гибридный поиск**: параллельное выполнение лексического (Elasticsearch) и семантического (Milvus) поиска
- **RRF объединение**: методом Reciprocal Rank Fusion для комбинирования результатов из разных источников
- **Двухуровневое переранжирование**: первый уровень RRF, второй уровень Cross-Encoder + бизнес-факторы
- **Intelliget Scoring**: multiplicative scoring model с учетом навыков, опыта, локации, зарплаты
- **Event-driven синхронизация**: автоматическая индексация при обновлении кандидатов через RabbitMQ

## Технологический стек

- **Framework**: FastAPI 0.118.0, Uvicorn с UVLoop
- **Search Engines**: Elasticsearch 8.11.0 + Milvus (семантический поиск)
- **ML Models**: Sentence Transformers `paraphrase-multilingual-mpnet-base-v2` + Cross-Encoder `ms-marco-MiniLM-L-6-v2`
- **Message Broker**: RabbitMQ с aio-pika (TOPIC exchange)
- **Observability**: Prometheus + OpenTelemetry + Structlog

## API Endpoints

### POST `/v1/search/next`

Возвращает лучшего кандидата на основе фильтров поиска.

**Request Body**:

```json
{
  "session_id": "50e68a2e-5e5c-47c3-8a0f-123456789abc",
  "filters": {
    "role": "Senior Python Developer",
    "must_skills": [{ "skill": "python", "level": 4 }],
    "nice_skills": [{ "skill": "kubernetes", "level": 3 }],
    "experience_min": 3,
    "experience_max": 15,
    "location": "Moscow",
    "work_modes": ["remote", "office"],
    "salary_min": 150000,
    "salary_max": 300000,
    "currency": "RUB",
    "english_level": "advanced",
    "exclude_ids": ["uuid1", "uuid2"]
  },
  "session_exclude_ids": ["uuid3"]
}
```

**Response** (Success):

```json
{
  "candidate": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "display_name": "Ivan Petrov",
    "headline_role": "Senior Python Developer",
    "experience_years": 5,
    "location": "Moscow",
    "salary_min": 150000,
    "salary_max": 250000,
    "currency": "RUB",
    "english_level": "advanced",
    "skills": [{ "skill": "python", "level": 5 }],
    "match_score": 0.8732,
    "explanation": {
      "ml_score": 0.8456,
      "skill_factor": 1.15,
      "exp_factor": 1.0,
      "loc_factor": 1.1,
      "sal_factor": 0.95,
      "eng_factor": 1.05
    }
  }
}
```

### POST `/v1/search/index/rebuild`

Запускает полную переиндексацию всех кандидатов (shadow index pattern).

**Response**:

```json
{
  "status": "accepted"
}
```

### GET `/health`

```json
{
  "status": "ok",
  "service": "search-service"
}
```

## Алгоритм поиска (4 этапа)

### Этап 1: Параллельный гибридный поиск

**Elasticsearch** (лексический):

- BM25 scoring по headline_role, skills, about_me
- Возвращает top-K ID (RETRIEVAL_SIZE=100)
- Fallback на пустой результат при ошибке

**Milvus** (семантический):

- Текст: `"{role} {must_skills} {nice_skills}"`
- Embedding: Sentence Transformers 768-dim
- Euclidean distance поиск + exclude_ids фильтр
- Graceful degradation при недоступности

### Этап 2: RRF (Reciprocal Rank Fusion)

```
combined_scores[id] += 1.0 / (k + rank + 1)  для каждого источника
```

Нормализует scores и объединяет результаты

### Этап 3: Получение полных документов

Mget из Elasticsearch для top-K из RRF (RERANK_TOP_K=20)

### Этап 4: L2 Переранжирование

**Cross-Encoder Score** → ML_Score (0-1)

**Multiplicative Model**:

```
Final = ML_Score × SkillFactor × ExpFactor × LocFactor × SalFactor × EngFactor
```

- **SkillFactor** (0.5-1.5): покрытие must_skills + бонус за nice_skills
  - **Must Skills**: сравнивает уровень требования работодателя с уровнем кандидата
    - Если `candidate_level >= required_level`: бонус `1.0 + (candidate_level - required_level) × 0.1`
    - Если `candidate_level < required_level`: штраф `1.0 - (required_level - candidate_level) × 0.2`
    - Итоговый: `FACTOR_NO_SKILLS + (1.0 - FACTOR_NO_SKILLS) × average_match`
  - **Nice Skills**: дополнительные навыки дают бонус
    - Если есть совпадение: `+0.1 + (candidate_level - required_level) × 0.05`
    - Max capped на 1.5
- **ExpFactor** (0.5-1.0): 15% штраф за год недостатка, 5% за переизбыток
- **LocFactor** (0.3-1.1): город + режим работы (remote/office)
- **SalFactor** (0.5-1.2): нормализация в RUB (USD=95, EUR=105)
- **EngFactor** (0.8-1.2): бонус за английский язык

## Event Processing

**RabbitMQ Consumer** слушает TOPIC exchange:

- `candidate.created` → индексировать в ES + Milvus
- `candidate.updated.profile` → переиндексировать
- `candidate.updated.#` → переиндексировать
- `candidate.deleted` → удалить из обоих

**Shadow Index**:

1. Incoming updates пишутся в основной индекс И в shadow
2. Background reindex пишет все кандидаты в shadow
3. После завершения: alias swap на shadow
4. Гарантирует: поиск работает без прерываний

## Конфигурация

```bash
# Elasticsearch
ELASTICSEARCH_URL="http://elasticsearch:9200"
CANDIDATE_INDEX_ALIAS="candidates"

# Milvus
MILVUS_HOST="milvus"
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME="candidate_embeddings"

# ML
SENTENCE_MODEL_NAME="paraphrase-multilingual-mpnet-base-v2"
RANKER_MODEL_NAME="cross-encoder/ms-marco-MiniLM-L-6-v2"

# Параметры поиска
RETRIEVAL_SIZE=100
RERANK_TOP_K=20
RRF_K=60

# Факторы
FACTOR_NO_SKILLS=0.5
FACTOR_EXP_MISMATCH=0.15
FACTOR_LOCATION_MATCH=0.1

# RabbitMQ
RABBITMQ_HOST="rabbitmq"
RABBITMQ_PORT=5672
RABBITMQ_USER="guest"
RABBITMQ_PASS="guest"
```

## Запуск

### Docker

```bash
docker build -t search-service .
docker run -p 8000:8000 search-service
```

### Локально

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Мониторинг

- **Prometheus**: `/metrics`
- **OpenTelemetry**: трейсинг всех операций
- **Structlog**: JSON логирование с контекстом
- **Rate Limiting**: через slowapi

## Тестирование

```bash
pytest tests/unit/ -v          # unit тесты
pytest tests/e2e/ -v           # E2E тесты
locust -f tests/locustfile.py  # Load тесты
```

## Интеграция

- **Candidate Service**: слищает события (RabbitMQ)
- **Employer Service**: вызывает `/next` API
- **Auth Service**: генерирует system токены

## Решение проблем

**Нерелевантные результаты**: проверить `RETRIEVAL_SIZE`, коэффициенты, очередь RabbitMQ

**Медленный поиск**: профилировать ES queries, масштабировать nodes

**Milvus недоступен**: graceful degradation, работает только ES

**События не обрабатываются**: проверить consumer logs, DLQ, routing keys

## Технологический стек

- **Framework**: FastAPI 0.118.0
- **Search Engines**:
  - Elasticsearch 8.11.0 (лексический поиск)
  - Milvus (векторный поиск)
- **ML Models**:
  - Sentence Transformers (paraphrase-multilingual-mpnet-base-v2) для эмбеддингов
  - Cross-Encoder (ms-marco-MiniLM-L-6-v2) для переранжирования
- **Message Broker**: RabbitMQ (aio-pika 9.5.7)
- **Rate Limiting**: slowapi
- **Observability**:
  - Prometheus (prometheus-fastapi-instrumentator)
  - OpenTelemetry (OTLP exporter)
  - Structlog для структурированного логирования

## API Endpoints

### POST `/v1/search/next`

Возвращает лучшего кандидата на основе фильтров поиска.

**Request Body**:

```json
{
  "session_id": "uuid",
  "filters": {
    "role": "string (обязательно)",
    "must_skills": ["skill1", "skill2"],
    "nice_skills": ["skill3", "skill4"],
    "experience_min": 0,
    "experience_max": 20,
    "location": "string",
    "work_modes": ["remote", "office"],
    "exclude_ids": ["uuid1", "uuid2"],
    "salary_min": 100000,
    "salary_max": 500000,
    "currency": "RUB",
    "english_level": "upper-intermediate",
    "about_me": "дополнительные критерии"
  },
  "session_exclude_ids": ["uuid3"]
}
```

**Response**:

```json
{
  "candidate": {
    "id": "uuid",
    "display_name": "string",
    "headline_role": "string",
    "experience_years": 5.5,
    "location": "Moscow",
    "salary_min": 150000,
    "salary_max": 300000,
    "currency": "RUB",
    "english_level": "intermediate",
    "about_me": "string",
    "skills": ["Python", "FastAPI"],
    "match_score": 0.85,
    "explanation": {
      "ml_score": 0.8,
      "skill_factor": 1.0,
      "exp_factor": 0.95,
      "location_factor": 1.0
    }
  }
}
```

### POST `/v1/search/index/rebuild`

Запускает полную переиндексацию всех кандидатов (асинхронно в фоне).

**Response**:

```json
{
  "status": "accepted"
}
```

### GET `/health`

Проверка здоровья сервиса.

**Response**:

```json
{
  "status": "ok",
  "service": "search-service"
}
```

## Event Processing

Сервис потребляет события из RabbitMQ для синхронизации данных кандидатов:

- `candidate.created` - индексирование нового кандидата
- `candidate.updated.*` - обновление данных кандидата
- `candidate.deleted` - удаление данных кандидата из индексов

При индексировании:

1. Документ записывается в Elasticsearch (основной и shadow индексы при переиндексации)
2. Текст кандидата конвертируется в embedding и записывается в Milvus

## Алгоритм поиска

### Этап 1: Гибридный поиск

- Параллельное выполнение поиска в ES и Milvus
- Каждый движок возвращает top-k ID документов

### Этап 2: RRF (Reciprocal Rank Fusion)

- Объединение результатов обоих поисков методом RRF:
  - Формула: `score = 1 / (k + rank + 1)` для каждого результата
  - Суммирование оценок для одного ID из разных источников
  - Сортировка по итоговой оценке

### Этап 3: Получение полных документов

- Получение полных данных кандидатов из Elasticsearch для top-k результатов из RRF

### Этап 4: L2 переранжирование

- Использование Cross-Encoder модели для оценки релевантности пары (query, candidate)
- **Multiplicative Scoring Model**:
  ```
  Final Score = ML_Score × SkillFactor × ExpFactor × LocationFactor
  ```
  где:
  - `ML_Score` - вероятность из Cross-Encoder (сигмоида)
  - `SkillFactor` - коэффициент покрытия обязательных навыков
  - `ExpFactor` - штраф за несоответствие опыта
  - `LocationFactor` - штраф за несоответствие локации

## Конфигурация

Переменные окружения (см. `app/core/config.py`):

- `ELASTICSEARCH_URL` - URL инстанса Elasticsearch
- `MILVUS_HOST`, `MILVUS_PORT` - параметры подключения к Milvus
- `MILVUS_COLLECTION_NAME` - имя коллекции в Milvus
- `SENTENCE_MODEL_NAME` - модель для генерации эмбеддингов
- `RANKER_MODEL_NAME` - модель для ранжирования
- `RETRIEVAL_SIZE` - количество результатов на этапе 1 поиска
- `RERANK_TOP_K` - количество результатов для переранжирования
- `RRF_K` - параметр k для RRF формулы
- `FACTOR_*` - коэффициенты для multiplicative scoring
- `RABBITMQ_*` - параметры подключения к RabbitMQ
- `SECRET_KEY`, `ALGORITHM` - для генерации system токенов

## Запуск

### Docker

```bash
docker build -t search-service .
docker run -p 8000:8000 search-service
```

### Локально

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Мониторинг

- **Prometheus метрики** доступны на `/metrics`
- **Структурированное логирование** через structlog
- **OpenTelemetry** предоставляет трейсинг для всех операций
- **Rate limiting** с помощью slowapi (настраивается через конфиг)

## Тестирование

```bash
pytest tests/
pytest --cov=app tests/  # с покрытием кода
```

Доступные тесты:

- `test_e2e_search.py` - end-to-end тесты поиска
- `test_indexer_extended.py` - тесты индексирования
- `test_integration_indexer.py` - интеграционные тесты
- `test_logic_extended.py` - тесты логики поиска
- `test_unit_logic.py` - unit тесты
