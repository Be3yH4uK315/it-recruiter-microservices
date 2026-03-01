# Bot Service

Telegram бот для IT посредничества. Позволяет кандидатам создавать профили и работодателям подбирать специалистов. Часть IT recruiter monorepo.

## Описание

Многофункциональный Telegram бот, обслуживающий два основных сценария:

1. **Кандидаты**: Регистрация профиля, редактирование, загрузка резюме и аватара
2. **Работодатели**: Поиск кандидатов по фильтрам, просмотр профилей

## Технологический стек

- **Bot Framework**: aiogram 3.5.0
- **State Management**: Redis (для FSM хранилища)
- **HTTP Client**: httpx с retry логикой (tenacity)
- **Data Validation**: Pydantic
- **Testing**: pytest, pytest-asyncio, respx
- **Performance Testing**: locust

## Архитектура

### Структура

```
app/
├── bot.py                # Главная точка входа, настройкаDispatcherа и middleware
├── core/
│   ├── config.py         # Конфигурация (токены, URL сервисов, Redis)
│   ├── messages.py       # Текстовые сообщения для всех сценариев
│   └── logger.py         # Логирование
├── handlers/             # Обработчики команд и callback'ов
│   ├── common.py         # /start и выбор роли
│   ├── candidate.py      # Регистрация и редактирование профиля кандидата
│   └── employer.py       # Поиск кандидатов работодателем
├── states/               # FSM состояния
│   ├── candidate.py      # CandidateFSM: регистрация, редактирование, загрузка файлов
│   └── employer.py       # EmployerSearch: фильтры и результаты
├── services/
│   ├── api_client.py     # HTTP клиенты для всех сервисов
│   └── auth_manager.py   # Управление токенами (Redis кеш + Auth Service)
├── keyboards/
│   └── inline.py         # Inline клавиатуры (кнопки выбора)
├── middlewares/
│   ├── fsm_timeout.py    # Очистка FSM после 30 минут неактивности
│   └── logging.py        # Логирование с ID пользователя
└── utils/
    ├── validators.py     # Валидация вводимых данных
    ├── formatters.py     # Форматирование профилей/сообщений
    └── processors.py     # Обработка текста
```

## Команды бота

### Общие команды
- `/start` - Начало работы, выбор роли (кандидат/работодатель)
- `/profile` - Просмотр или редактирование своего профиля (для кандидатов)
- `/search` - Начало поиска кандидатов (для работодателей)

## FSM States

### Для кандидатов (CandidateFSM)

| Состояние | Назначение |
|-----------|-----------|
| `entering_basic_info` | Ввод имени, роли, локации, режимов работы |
| `block_entry` | Ввод опыта, навыков, проектов, образования |
| `selecting_options` | Выбор: режимы работы, уровни навыков, уровни английского |
| `confirm_action` | Подтверждение: добавить еще, начать регистрацию |
| `uploading_file` | Загрузка резюме или аватара |
| `choosing_field` | Выбор поля для редактирования |
| `editing_contacts` | Редактирование контактной информации |
| `showing_profile` | Финальный просмотр профиля |

### Для работодателей (EmployerSearch)

| Состояние | Назначение |
|-----------|-----------|
| `entering_company_name` | Ввод названия компании (при первом входе) |
| `entering_filters` | Ввод критериев поиска (роль, навыки, опыт, локация и т.д.) |
| `showing_results` | Просмотр результатов поиска |

## API Integration

Бот взаимодействует с несколькими микросервисами:

### Auth Service
- `POST /v1/auth/login/bot` - получение Access Token для пользователя

### Candidate Service
- `POST /candidates/` - регистрация нового кандидата
- `GET /candidates/{id}` - получение профиля кандидата
- `PATCH /candidates/{id}` - обновление профиля
- и другие операции (опыт, навыки, образование, загрузка файлов)

### Employer Service
- `GET /employers/` - получение/создание профиля работодателя
- `PATCH /employers/{id}` - обновление профиля

### Search Service
- `POST /v1/search/next` - получение следующего кандидата по фильтрам

### File Service
- `POST /files/upload` - загрузка резюме или аватара
- `GET /files/{id}/download-url` - получение URL для скачивания

## Authentication

1. Пользователь взаимодействует с ботом через Telegram
2. Бот отправляет `telegram_id` и `bot_secret` в Auth Service
3. Auth Service возвращает `access_token`
4. Токен кешируется в Redis с TTL
5. Все последующие запросы к API используют этот токен

**Auth Manager** (`services/auth_manager.py`):
- Проверяет наличие валидного токена в Redis
- При отсутствии - запрашивает новый в Auth Service
- Сохраняет токен с корректной TTL

## Middleware

### FSMTimeoutMiddleware
- Отслеживает время последней активности пользователя
- При неактивности более 30 минут очищает FSM состояние
- Уведомляет пользователя о таймауте

### LoggingMiddleware
- Логирует все сообщения и callback запросы с ID пользователя
- Помогает отследить проблемы пользователя

## Профиль кандидата

Бот позволяет собирать следующую информацию:

- **Базовая информация**: ФИО, должность, локация, режимы работы
- **Опыт работы**: Компания, должность, даты, описание обязанностей (до 5 записей)
- **Навыки**: Название, тип (язык, инструмент и т.д.), уровень (1-5) (до 20 записей)
- **Проекты**: Название, описание (до 5 записей)
- **Образование**: Уровень, учебное заведение, год окончания (до 5 записей)
- **Файлы**: Резюме (PDF), аватар (JPG/PNG)
- **Контакты**: Телефон, email, LinkedIn, GitHub (с опциональной видимостью)

## Профиль работодателя

- **Компания**: Название (обязательное при первом входе)
- **Фильтры поиска**:
  - Должность (обязательно)
  - Обязательные навыки
  - Желаемые навыки
  - Опыт (мин-макс)
  - Локация
  - Режимы работы
  - Зарплата (мин-макс)
  - Уровень английского

## Запуск

### Docker
```bash
docker build -t bot-service .
docker run bot-service
```

### Локально
```bash
pip install -r requirements.txt
python app/bot.py
```

## Конфигурация

Переменные окружения (см. `app/core/config.py`):
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота (@BotFather)
- `ADMIN_IDS` - список ID администраторов (запятая-разделенные)
- `INTERNAL_BOT_SECRET` - secret для Auth Service
- `AUTH_SERVICE_URL` - URL auth сервиса
- `CANDIDATE_SERVICE_URL` - URL candidate сервиса
- `EMPLOYER_SERVICE_URL` - URL employer сервиса
- `SEARCH_SERVICE_URL` - URL search сервиса
- `FILE_SERVICE_URL` - URL file сервиса
- `REDIS_HOST` - хост Redis
- `REDIS_PORT` - порт Redis
- `LOG_LEVEL` - уровень логирования (INFO, DEBUG, ERROR)
- `LOG_FILE` - путь к файлу логов

## Тестирование

```bash
pytest tests/
pytest --cov=app tests/  # с покрытием кода
```

Доступные тесты:
- `test_api_client.py` - тесты API клиентов
- `test_candidate_flow.py` - сценарий регистрации кандидата
- `test_candidate_blocks.py` - тесты отдельных блоков профиля
- `test_employer_search.py` - сценарий поиска кандидатов
- `test_handlers_extended.py` - расширенные тесты обработчиков
- `test_utils.py` - утилиты и валидаторы
- `test_profile_view.py` - отображение профиля
- `test_common.py` - общие функции

## Rate Limiting

Бот использует встроенные ограничения Telegram API. Дополнительные ограничения можно добавить через добавление rate limiter middleware.

## Обработка ошибок

### API ошибки
- **Network Error**: Автоматический retry (exponential backoff, max 3 попытки)
- **HTTP Error**: Логирование и уведомление пользователя
- **Session Timeout**: Очистка FSM, уведомление пользователя

### Валидация
- Проверка длины строк
- Валидация дат (формат ГГГГ-ММ-ДД)
- Проверка номеров телефонов (E.164 формат)
- Размер файлов (резюме до 10 МБ, аватар до 5 МБ)

## Логирование

- **Структурированное логирование** с ID пользователя
- **Rotating file handler**: 5 МБ на файл, до 5 файлов
- **Разные уровни**: DEBUG, INFO, WARNING, ERROR для разных компонентов
