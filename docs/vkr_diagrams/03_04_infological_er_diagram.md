# Рисунок 3.4. Инфологическая ER-диаграмма основных сущностей платформы

Диаграмма построена по фактическим ORM-моделям и Alembic-миграциям сервисов `auth`, `candidate`, `employer`, `bot` и `file`.

Технические таблицы `outbox_messages`, `idempotency_keys`, `callback_contexts`, `processed_updates` и аналогичные служебные структуры исключены, поскольку они не относятся напрямую к предметной модели подбора персонала.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Times New Roman",
    "fontSize": "14px",
    "primaryTextColor": "#000000",
    "lineColor": "#000000",
    "tertiaryColor": "#f7f7f7",
    "mainBkg": "#fdfdfd",
    "background": "#ffffff"
  }
}}%%
erDiagram
    AUTH_USERS {
        UUID id
        BIGINT telegram_id
        STRING username
        STRING first_name
        STRING last_name
        TEXT photo_url
        STRING role
        BOOLEAN is_active
        DATETIME created_at
        DATETIME updated_at
    }

    AUTH_USER_ROLES {
        UUID user_id
        STRING role
        DATETIME created_at
    }

    AUTH_REFRESH_SESSIONS {
        UUID id
        UUID user_id
        STRING token_hash
        DATETIME expires_at
        BOOLEAN revoked
        DATETIME created_at
    }

    CANDIDATES {
        UUID id
        BIGINT telegram_id
        STRING display_name
        STRING headline_role
        STRING location
        ARRAY work_modes
        INT salary_min
        INT salary_max
        STRING currency
        STRING contacts_visibility
        JSON contacts
        STRING status
        STRING english_level
        TEXT about_me
        UUID avatar_file_id
        UUID resume_file_id
        DATETIME created_at
        DATETIME updated_at
        INT version_id
    }

    CANDIDATE_SKILLS {
        UUID id
        UUID candidate_id
        STRING skill
        STRING kind
        INT level
    }

    CANDIDATE_EDUCATION {
        UUID id
        UUID candidate_id
        STRING level
        STRING institution
        INT year
    }

    CANDIDATE_EXPERIENCES {
        UUID id
        UUID candidate_id
        STRING company
        STRING position
        DATE start_date
        DATE end_date
        TEXT responsibilities
    }

    CANDIDATE_PROJECTS {
        UUID id
        UUID candidate_id
        STRING title
        TEXT description
        JSON links
    }

    EMPLOYERS {
        UUID id
        BIGINT telegram_id
        STRING company
        JSON contacts
        UUID avatar_file_id
        UUID document_file_id
        DATETIME created_at
        DATETIME updated_at
    }

    SEARCH_SESSIONS {
        UUID id
        UUID employer_id
        STRING title
        JSON filters
        INT search_offset
        INT search_total
        STRING status
        DATETIME created_at
        DATETIME updated_at
    }

    SEARCH_SESSION_CANDIDATES {
        UUID id
        UUID session_id
        UUID candidate_id
        INT rank_position
        STRING display_name
        STRING headline_role
        FLOAT experience_years
        STRING location
        JSON skills
        INT salary_min
        INT salary_max
        STRING currency
        STRING english_level
        TEXT about_me
        FLOAT match_score
        JSON explanation
        BOOLEAN is_consumed
        DATETIME created_at
    }

    DECISIONS {
        UUID id
        UUID session_id
        UUID candidate_id
        STRING decision
        TEXT note
        DATETIME created_at
    }

    CONTACT_REQUESTS {
        UUID id
        UUID employer_id
        UUID candidate_id
        STRING status
        DATETIME responded_at
        DATETIME created_at
    }

    FILES {
        UUID id
        STRING owner_service
        UUID owner_id
        STRING category
        STRING filename
        STRING content_type
        STRING bucket
        STRING object_key
        STRING status
        INT size_bytes
        DATETIME created_at
        DATETIME updated_at
        DATETIME deleted_at
        INT version_id
    }

    TELEGRAM_ACTORS {
        BIGINT telegram_user_id
        STRING username
        STRING first_name
        STRING last_name
        STRING language_code
        BOOLEAN is_bot
        DATETIME created_at
        DATETIME updated_at
    }

    BOT_SESSIONS {
        UUID id
        BIGINT telegram_user_id
        UUID auth_user_id
        STRING active_role
        TEXT access_token
        TEXT refresh_token
        STRING token_type
        DATETIME access_token_expires_at
        BOOLEAN is_authorized
        DATETIME last_login_at
        DATETIME last_refresh_at
        DATETIME created_at
        DATETIME updated_at
    }

    CONVERSATION_STATES {
        BIGINT telegram_user_id
        STRING role_context
        STRING state_key
        INT state_version
        JSON payload
        DATETIME updated_at
    }

    DIALOG_RENDER_STATES {
        BIGINT telegram_user_id
        BIGINT chat_id
        INT primary_message_id
        JSON attachment_message_ids
        DATETIME updated_at
    }

    DRAFT_PAYLOADS {
        UUID id
        BIGINT telegram_user_id
        STRING draft_type
        STRING role_context
        JSON payload
        STRING status
        DATETIME created_at
        DATETIME updated_at
    }

    PENDING_UPLOADS {
        UUID id
        BIGINT telegram_user_id
        STRING role_context
        STRING target_service
        STRING target_kind
        UUID owner_id
        UUID file_id
        TEXT telegram_file_id
        TEXT telegram_file_unique_id
        TEXT filename
        STRING content_type
        STRING status
        TEXT error_message
        DATETIME created_at
        DATETIME updated_at
    }

    AUTH_USERS ||--o{ AUTH_USER_ROLES : "FK user_id"
    AUTH_USERS ||--o{ AUTH_REFRESH_SESSIONS : "FK user_id"

    CANDIDATES ||--o{ CANDIDATE_SKILLS : "FK candidate_id"
    CANDIDATES ||--o{ CANDIDATE_EDUCATION : "FK candidate_id"
    CANDIDATES ||--o{ CANDIDATE_EXPERIENCES : "FK candidate_id"
    CANDIDATES ||--o{ CANDIDATE_PROJECTS : "FK candidate_id"

    EMPLOYERS ||--o{ SEARCH_SESSIONS : "FK employer_id"
    SEARCH_SESSIONS ||--o{ SEARCH_SESSION_CANDIDATES : "FK session_id"
    SEARCH_SESSIONS ||--o{ DECISIONS : "FK session_id"
    EMPLOYERS ||--o{ CONTACT_REQUESTS : "FK employer_id"

    AUTH_USERS ||--o| CANDIDATES : "LOG telegram_id"
    AUTH_USERS ||--o| EMPLOYERS : "LOG telegram_id"
    CANDIDATES ||--o{ SEARCH_SESSION_CANDIDATES : "LOG candidate_id"
    CANDIDATES ||--o{ DECISIONS : "LOG candidate_id"
    CANDIDATES ||--o{ CONTACT_REQUESTS : "LOG candidate_id"
    SEARCH_SESSION_CANDIDATES ||--o| DECISIONS : "LOG session_id+candidate_id"
    CANDIDATES ||--o{ FILES : "LOG owner_id/file_id"
    EMPLOYERS ||--o{ FILES : "LOG owner_id/file_id"

    TELEGRAM_ACTORS ||--o| BOT_SESSIONS : "LOG telegram_user_id"
    TELEGRAM_ACTORS ||--o| CONVERSATION_STATES : "LOG telegram_user_id"
    TELEGRAM_ACTORS ||--o| DIALOG_RENDER_STATES : "LOG telegram_user_id"
    TELEGRAM_ACTORS ||--o{ DRAFT_PAYLOADS : "LOG telegram_user_id"
    TELEGRAM_ACTORS ||--o{ PENDING_UPLOADS : "LOG telegram_user_id"
    FILES ||--o{ PENDING_UPLOADS : "LOG file_id"
```

Условные обозначения:

- `FK` — физическая связь на уровне БД, закрепленная внешним ключом.
- `LOG` — логическая связь, существующая на уровне предметной области и кода приложения, но не закрепленная внешним ключом в одной БД.
