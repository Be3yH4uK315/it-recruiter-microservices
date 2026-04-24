# Рисунок А.1. Вход и авторизация через Telegram

Диаграмма отражает фактический сценарий обработки команды `/start`: сначала бот показывает выбор роли или предлагает продолжить незавершенный сценарий, а внутренний `login via bot` выполняется после выбора роли.

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
    participant DB as bot PostgreSQL
    participant AUTH as auth-service

    U->>TG: Команда /start
    TG->>BOT: webhook-обновление
    BOT->>DB: Проверка состояния беседы и сессии бота

    alt Есть незавершенный сценарий
        DB-->>BOT: Найдено состояние диалога
        BOT-->>TG: Предложение продолжить или сбросить сценарий
    else Незавершенного сценария нет
        DB-->>BOT: Состояние не найдено
        BOT-->>TG: Экран выбора роли
        U->>TG: Нажатие кнопки роли
        TG->>BOT: callback выбора роли
        BOT->>AUTH: POST /api/v1/auth/login/bot
        AUTH-->>BOT: access и refresh токены
        BOT->>DB: Сохранение сессии бота
        BOT->>BOT: Загрузка выбранной роли

        alt Профиль роли уже существует
            BOT-->>TG: Отрисовка кабинета
        else Профиль роли отсутствует
            BOT->>DB: Сохранение первого шага регистрации
            BOT-->>TG: Запрос первого поля профиля
        end
    end
```
