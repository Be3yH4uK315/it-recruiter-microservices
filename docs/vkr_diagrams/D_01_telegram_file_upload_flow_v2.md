# Рисунок Д.1. Загрузка файлов через Telegram

Диаграмма отражает фактический сценарий загрузки: после передачи файла в объектное хранилище `candidate-service` или `employer-service` дополнительно вызывает `file-service` для активации файла через `/complete`, и только затем связывает `file_id` с профилем.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Times New Roman",
    "fontSize": "14px",
    "primaryTextColor": "#000000",
    "lineColor": "#000000",
    "signalColor": "#000000",
    "activationBkgColor": "#f1f3f5",
    "activationBorderColor": "#000000"
  }
}}%%
sequenceDiagram
    autonumber
    actor U as Пользователь
    participant TG as Telegram
    participant BOT as bot-service
    participant GW as candidate-service или employer-service
    participant FILE as file-service
    participant MINIO as объектное хранилище
    participant DB as bot pending_uploads

    U->>TG: Отправить фото или документ
    TG-->>BOT: Сообщение с telegram file_id
    BOT->>GW: Запрос upload-url
    GW->>FILE: POST /api/v1/internal/files/upload-url
    FILE-->>GW: presigned upload URL и file_id
    GW-->>BOT: Данные загрузки
    BOT->>DB: Создание записи pending_upload
    BOT->>TG: Скачивание файла из Telegram
    BOT->>DB: Статус загружено из Telegram
    BOT->>MINIO: Загрузка по presigned URL
    BOT->>DB: Статус загруженно в хранилище
    BOT->>GW: Запрос замены с file_id
    GW->>FILE: POST /api/v1/internal/files/{file_id}/complete
    FILE-->>GW: Файл активирован
    GW->>GW: Валидация метаданных и привязка file_id к сущности
    GW-->>BOT: Файл привязан к профилю
    BOT->>DB: Статус загрузки
```
