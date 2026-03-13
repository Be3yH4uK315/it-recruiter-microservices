# File Service

Микросервис управления файлами (резюме, аватары). Обеспечивает загрузку, скачивание файлов через S3/MinIO с presigned URLs и метаданными в БД.

## Описание

Основная функциональность:
- **Загрузка файлов**: в S3/MinIO с сохранением метаданных (размер, тип, владелец)
- **Валидация**: проверка файлов по Magic Bytes (не по расширению), поддержка PDF, JPEG, PNG
- **Presigned URLs**: временные ссылки для скачивания/загрузки (TTL 1 час)
- **Удаление файлов**: трансакционное удаление из S3 и БД с проверкой прав
- **Типизация**: раздельное хранилище для резюме и аватаров (`{type}s/{telegram_id}/{uuid}.{ext}`)
- **Контроль доступа**: только владелец файла может его удалить
- **Domain rewriting**: поддержка CDN через S3_PUBLIC_DOMAIN конфиг

## Технологический стек

- **Framework**: FastAPI 0.116.1, Uvicorn с UVLoop
- **Database**: PostgreSQL 15 (SQLAlchemy 2.0.43 + asyncpg)
- **Storage**: S3/MinIO (aioboto3 10.4.0)
- **Security**: filetype для анализа Magic Bytes
- **Observability**: Prometheus + OpenTelemetry + Structlog

## API Endpoints

### POST `/v1/files/upload`
Загрузка файла на сервер.

**Request (multipart/form-data)**:
```
file: <binary>              # Сам файл
file_type: "resume"         # Тип: "resume", "avatar"
Authorization: Bearer <token>
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "filename": "resume.pdf",
  "content_type": "application/pdf",
  "size_bytes": 102400,
  "created_at": "2026-02-28T10:30:00Z"
}
```

**Логика**:
1. Требует валидного JWT токена в заголовке Authorization
2. Извлекает `owner_telegram_id` из токена
3. Читает первые 2048 байт (Magic Bytes) и проверяет, что файл действительно является изображением (JPG/PNG) или документом (PDF/DOCX).
4. Генерирует уникальный ID файла (UUID)
5. Сохраняет в S3 с ключом: `{file_type}s/{telegram_id}/{uuid}.{ext}`
6. Записывает метаданные в БД (PostgreSQL)
7. Возвращает ID файла и информацию

**Примеры использования**:

```bash
# Загрузка резюме
curl -X POST /v1/files/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@resume.pdf" \
  -F "file_type=resume"

# Загрузка аватара
curl -X POST /v1/files/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@avatar.jpg" \
  -F "file_type=avatar"
```

### GET `/v1/files/{file_id}/url`
Получение временной ссылки для скачивания файла.

**Response**:
```json
{
  "download_url": "https://storage.example.com/files/...?signature=...&expires=..."
}
```

**Особенности**:
- Ссылка действительна 1 час (по умолчанию)
- Не требует авторизации - ссылка уникальна и защищена подписью
- Может быть отправлена в Telegram, email и т.д.
- Если configurирован `S3_PUBLIC_DOMAIN` - ссылка переписывается на публичный домен

**Пример**:
```bash
curl /v1/files/550e8400-e29b-41d4-a716-446655440000/url

# Ответ:
{
  "download_url": "https://cdn.minio.example.com/resumes/123456789/uuid.pdf?..."
}
```

### DELETE `/v1/files/{file_id}`
Удаление файла (только владелец).

**Request**:
```
Authorization: Bearer <token>
```

**Response**:
```json
{
  "status": "deleted"
}
```

**Логика**:
1. Проверяет, что требестель - владелец файла
2. Удаляет файл из S3
3. Удаляет запись из БД
4. Логирует попытки несанкционированного доступа

**Примеры ошибок**:
- `403 Forbidden` - не владелец файла
- `404 Not Found` - файл не существует

### GET `/health`
Проверка здоровья сервиса.

**Response**:
```json
{
  "status": "ok"
}
```

## Database Schema

### files таблица
```
id (UUID) - Primary key, также используется как file_id в API
owner_telegram_id (BigInt) - ID владельца (из токена), индекс
filename (String) - Оригинальное имя файла от пользователя
content_type (String) - MIME тип (application/pdf, image/jpeg и т.д.)
size_bytes (Integer) - Размер файла в байтах
s3_key (String) - Ключ для S3 (уникальный), формат: {file_type}s/{telegram_id}/{id}.{ext}
bucket (String) - Имя бакета S3 (из конфига)
file_type (String) - Тип файла (resume, avatar и т.д.) для группировки
created_at (DateTime) - Время загрузки
```

## S3/MinIO Integration

### Структура хранилища
```
s3-bucket/
├── resumes/
│   ├── 123456789/
│   │   ├── uuid1.pdf
│   │   └── uuid2.pdf
│   └── 987654321/
│       └── uuid3.pdf
└── avatars/
    ├── 123456789/
    │   └── uuid4.jpg
    └── 987654321/
        └── uuid5.png
```

### Конфигурация
- **Endpoint**: `S3_ENDPOINT_URL` (может быть S3 AWS, MinIO и т.д.)
- **Публичный домен**: `S3_PUBLIC_DOMAIN` (опционально, для переписания ссылок на CDN)
- **Credentials**: `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- **Регион**: `S3_REGION`
- **Бакет**: `S3_BUCKET_NAME`

### Presigned URL

Временные ссылки генерируются алгоритмом AWS S3:
- **TTL**: 3600 сек (1 час) по умолчанию
- **Подпись**: включает access key, timestamp, policy
- **Безопасность**: нельзя подделать без secret key
- **Публичный домен**: если настроен, ссылка переписывается (например, на CloudFront CDN)

**Пример с переписыванием домена**:
```
S3_ENDPOINT_URL: https://minio.internal:9000
S3_PUBLIC_DOMAIN: https://cdn.minio.example.com

Сгенерированная URL:
https://minio.internal:9000/bucket/key?...

После переписывания:
https://cdn.minio.example.com/bucket/key?...
```

## Интеграция с другими сервисами

### Candidate Service
1. Получает `presigned_url` для загрузки резюме:
   ```
   POST /candidates/{id}/resume/upload-url
   ```
2. Загружает файл в S3 напрямую (без Candidate Service)
3. Отправляет file_id обратно в Candidate Service:
   ```
   PUT /candidates/{id}/resume
   ```

### Bot Service
1. Когда кандидат загружает аватар через Telegram бота
2. Файл отправляется на File Service
3. File Service возвращает file_id
4. Bot передает file_id в Candidate Service

### Search Service
1. Получает URL аватара кандидата для отображения в боте через File Service

## Конфигурация

Переменные окружения (см. `app/core/config.py`):
- `DATABASE_URL` - PostgreSQL (формат: `postgresql+asyncpg://user:pass@host/db`)
- `S3_ENDPOINT_URL` - URL S3/MinIO сервера (например: `https://minio.example.com:9000`)
- `S3_PUBLIC_DOMAIN` - Публичный домен для переписывания ссылок (опционально)
- `S3_ACCESS_KEY` - Access key для S3
- `S3_SECRET_KEY` - Secret key для S3
- `S3_BUCKET_NAME` - Имя бакета
- `S3_REGION` - Регион S3
- `MAX_FILE_SIZE` - Максимальный размер файла (в байтах)
- `SECRET_KEY`, `ALGORITHM` - для подписи JWT токенов
- `LOG_LEVEL` - уровень логирования

## Запуск

### Docker
```bash
docker build -t file-service .
docker run -p 8000:8000 file-service
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
- `test_e2e.py` - end-to-end тесты загрузки и скачивания
- `test_integration.py` - интеграционные тесты с S3
- `test_s3_client_unit.py` - unit тесты S3 клиента
- `test_dependencies.py` - тесты dependency injection
- `test_unit.py` - unit тесты основных компонентов

## Мониторинг

- **Prometheus метрики** на `/metrics`
- **OpenTelemetry** для трейсинга операций
- **Structlog** для структурированного логирования с контекстом файла

## Обработка ошибок

### Загрузка
- `400 Bad Request` - отсутствует file или file_type
- `401 Unauthorized` - неверный или отсутствующий токен
- `413 Payload Too Large` - файл больше `MAX_FILE_SIZE`
- `502 Bad Gateway` - ошибка S3 при загрузке

### Скачивание
- `404 Not Found` - файл не существует
- `502 Bad Gateway` - ошибка S3 при генерации URL

### Удаление
- `403 Forbidden` - не владелец файла
- `404 Not Found` - файл не существует

### S3 операции
- Автоматическое создание бакета при (первом запуске (если не существует))
- Логирование всех ошибок S3
- Graceful degradation - если S3 недоступен, возвращается 502

## Безопасность

### Аутентификация
- Все операции требуют валидный JWT токен в заголовке Authorization
- `owner_telegram_id` извлекается из токена
- Используется для контроля доступа при удалении

### Контроль доступа
- **Загрузка**: доступна аутентифицированным пользователям
- **Скачивание**: доступна всем, но только по presigned URL (защита подписью)
- **Удаление**: только владелец (проверка `owner_telegram_id`)

### Хранилище
- Файлы хранятся в private S3 бакете
- Доступ только через APIs (не публичный)
- Метаданные в защищенной БД

## Performance

### Оптимизизация загрузки
- Потоковая загрузка в S3 (не весь файл в памяти)
- Асинхронные операции (aioboto3)

### Кеширование
- Presigned URL кешируется на клиенте
- TTL 1 час от момента генерации

### Масштабируемость
- Безгранично масштабируемое S3/MinIO хранилище
- Асинхронные операции для конкурентности
- Connection pooling для БД чтений/записей
