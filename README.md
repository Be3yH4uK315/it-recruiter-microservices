# IT Recruiter Platform

Монорепозиторий платформы подбора IT-кандидатов: Telegram-бот, микросервисы на FastAPI, гибридный поиск (Elasticsearch + Milvus), событийная интеграция через RabbitMQ.

## Обзор

Система состоит из 6 сервисов:
- `auth`: аутентификация, JWT, internal auth.
- `candidate`: профиль кандидата, выдача данных в поиск.
- `employer`: профиль работодателя, сессии поиска, контактные сценарии.
- `file`: загрузка/выдача файлов через S3/MinIO.
- `search`: гибридный поиск, RRF, переранжирование.
- `bot`: Telegram webhook API и оркестрация пользовательских сценариев.

Ключевые инженерные паттерны:
- outbox worker для событий.
- idempotency middleware для безопасных повторов.
- circuit breaker на межсервисных вызовах.
- structured logging + OpenTelemetry + Prometheus.

## Архитектура

Инфраструктура в `docker-compose.yaml`:
- `postgres` (единый инстанс, отдельные БД под сервисы).
- `rabbitmq`.
- `search-elasticsearch`, `search-milvus` (+ `search-etcd`, `search-minio`).
- `file-minio`.
- `nginx` как API gateway.
- `prometheus`, `grafana`, `jaeger`.
- `ngrok` для внешнего webhook (опционально).

Важно: Redis в текущем `docker-compose.yaml` не используется.

## Порты И Эндпоинты

Внешние порты API:
- `80` -> Nginx gateway.
- `8001` -> `auth-api`.
- `8002` -> `candidate-api`.
- `8003` -> `employer-api`.
- `8004` -> `file-api`.
- `8005` -> `search-api`.
- `8010` -> `bot-api`.

Health-check:
- Gateway: `GET http://localhost/health`
- Сервисы: `GET http://localhost:<port>/api/v1/health`

Маршрутизация через Nginx (`infrastructure/nginx/conf.d/default.conf`):
- `/api/v1/auth/` -> `auth-api`
- `/api/v1/candidates/` -> `candidate-api`
- `/api/v1/employers/` -> `employer-api`
- `/api/v1/files/` -> `file-api`
- `/api/v1/search/` -> `search-api`
- `/api/v1/telegram/` -> `bot-api`
- `/files/` -> `file-minio`

## Быстрый Старт

```bash
git clone <repo>
cd it_recruiter_monorepo
cp .env.example .env

# Сервисные настройки храним в services/*/.env (gitignored):
cp services/auth/.env.example services/auth/.env
cp services/bot/.env.example services/bot/.env
cp services/candidate/.env.example services/candidate/.env
cp services/employer/.env.example services/employer/.env
cp services/file/.env.example services/file/.env
cp services/search/.env.example services/search/.env

docker compose up -d --build
```

Проверка:

```bash
curl http://localhost/health
curl http://localhost:8001/api/v1/health
curl http://localhost:8002/api/v1/health
curl http://localhost:8003/api/v1/health
curl http://localhost:8004/api/v1/health
curl http://localhost:8005/api/v1/health
curl http://localhost:8010/api/v1/health
```

## Конфигурация

- Корневой `.env` используется для compose-level переменных (сейчас: `NGROK_AUTHTOKEN`).
- `services/*/.env` — единственный источник конфигурации сервиса и для локального запуска, и для Docker Compose.
- `services/*/.env.example` — шаблон для заполнения.
- Корневой `.env` остаётся только для compose-level переменных, например `NGROK_AUTHTOKEN`.

Рекомендации:
- не хранить реальные токены в git;
- для локальной разработки использовать безопасные тестовые значения;
- для прода — секрет-хранилище и ротация ключей.

## Тестирование

Unit-тесты по всем сервисам:

```bash
for s in auth bot candidate employer file search; do
  (cd services/$s && .venv/bin/pytest tests/unit -q)
done
```

Интеграционные тесты (по умолчанию отключены в `conftest.py`, включаются через `RUN_INTEGRATION=1`):

```bash
for s in auth candidate employer file search; do
  (cd services/$s && RUN_INTEGRATION=1 .venv/bin/pytest tests/integration -q)
done
```

E2E сценарий поиска:

```bash
cd services/search
RUN_INTEGRATION=1 .venv/bin/pytest tests/integration/e2e/test_search_pipeline.py -q
```

## Нагрузочное Тестирование

Запуск теперь делается из папки конкретного сервиса. Примеры:

```bash
docker compose -f docker-compose.yaml -f docker-compose.loadtest.yaml up -d --build

cd services/search
.venv/bin/python -m loadtests.run --profile baseline

cd services/auth
.venv/bin/python -m loadtests.run --profile smoke
```

В каждом `services/<service>/loadtests` лежат:
- `locustfile.py`
- `common.py`
- `run.py`
- `profiles/*.json`

## Observability

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Jaeger: `http://localhost:16686`

Метрики сервисов доступны на `/metrics` каждого API-контейнера.

## CI/CD (текущее состояние)

- `CI` workflow:
  - lint (`black`, `isort`, `flake8`),
  - baseline type-check (`mypy`) по ключевым входным и runtime-модулям сервисов,
  - unit/integration-like прогоны тестов по сервисам с `--cov-fail-under=50`,
  - для `pull_request` проверки запускаются только для измененных сервисов,
  - scheduled/manual integration job,
  - сборка docker-образов на `push`.
- `Security` workflow:
  - dependency review для PR,
  - `pip-audit` по requirements-файлам.

Пайплайнов деплоя в production/staging в текущем репозитории нет.

## План Доведения

Актуальный рабочий план: [docs/project_completion_plan.md](./docs/project_completion_plan.md)

## Лицензия

Проприетарное ПО. Все права защищены.
