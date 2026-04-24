# Рисунок Г.1. Поиск кандидатов и обработка запросов на контакты

Диаграмма отражает текущую реализацию: `employer-service` сначала использует локальный пул кандидатов, а запрос контактов может завершиться сразу или перейти в `pending` в зависимости от `contacts_visibility`.

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
    actor E as Работодатель
    participant BOT as bot-service
    participant EMP as employer-service
    participant SEARCH as search-service
    participant CAND as candidate-service
    actor C as Кандидат

    E->>BOT: Открыть поисковую сессию
    BOT->>EMP: Запрос следующего кандидата

    alt В локальном пуле есть кандидат
        EMP->>EMP: Чтение следующего кандидата из search_session_candidates
    else Локальный пул пуст
        EMP->>SEARCH: POST /api/v1/search/candidates
        SEARCH-->>EMP: Пакет найденных кандидатов
        EMP->>EMP: Пополнение локального пула
    end

    EMP->>CAND: GET профиль кандидата
    CAND-->>EMP: Карточка кандидата
    EMP-->>BOT: Данные кандидата
    BOT-->>E: Отображение карточки

    E->>BOT: Выбрать решение по кандидату
    BOT->>EMP: Сохранить решение
    EMP-->>BOT: Решение сохранено

    E->>BOT: Запросить контакты
    BOT->>EMP: Создать запрос на контакты

    alt contacts_visibility = public
        EMP-->>BOT: Контакты доступны сразу
        BOT-->>E: Показать контакты
    else contacts_visibility = hidden
        EMP-->>BOT: Доступ отклонен сразу
        BOT-->>E: Показать отказ
    else contacts_visibility = on_request
        EMP-->>BOT: Статус ожидания
        BOT-->>E: Показать ожидание решения кандидата

        Note over C,BOT: Только ожидающие запросы попадают в кабинет кандидата
        C->>BOT: Открыть список ожидающих запросов
        BOT->>EMP: Получить запросы ожидающие решенения
        EMP-->>BOT: Список запросов
        C->>BOT: Одобрить или отклонить запрос
        BOT->>EMP: Передать решение кандидата
        EMP-->>BOT: Обновленный статус
        BOT-->>C: Отобразить итог решения
    end
```
