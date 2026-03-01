# Search Service

Микросервис поиска и подбора кандидатов на основе гибридного поиска (лексический + семантический). Часть IT recruiter monorepo.

## Описание

Сервис реализует подбор подходящих кандидатов для вакансий на основе:
- **Полнотекстового поиска** через Elasticsearch (лексический поиск)
- **Семантического поиска** через Milvus с использованием embedding моделей
- **Гибридного ранжирования** методом RRF (Reciprocal Rank Fusion)
- **Двухуровневого переранжирования** с применением Cross-Encoder моделей

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
