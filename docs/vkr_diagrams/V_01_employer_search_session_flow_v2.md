# Рисунок В.1. Создание поисковой сессии работодателя

Диаграмма отражает фактическую логику мастера: на экране подтверждения можно вернуться к выбранному шагу, а после успешного создания бот открывает экран созданной сессии.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Times New Roman",
    "fontSize": "14px",
    "primaryTextColor": "#000000",
    "lineColor": "#000000"
  },
  "flowchart": {
    "curve": "linear",
    "nodeSpacing": 24,
    "rankSpacing": 34
  }
}}%%
flowchart TD
    START["Запуск мастера создания поиска"]:::step --> TITLE["Название поисковой сессии"]:::step
    TITLE --> ROLE["Профессиональная роль"]:::step
    ROLE --> MUST["Обязательные навыки"]:::step
    MUST --> NICE["Желательные навыки"]:::step
    NICE --> EXP["Требуемый опыт"]:::step
    EXP --> LOC["Локация"]:::step
    LOC --> MODE["Формат работы"]:::step
    MODE --> SAL["Зарплатный диапазон"]:::step
    SAL --> ENG["Уровень английского"]:::step
    ENG --> DESC["Описание поиска"]:::step
    DESC --> CONFIRM["Экран подтверждения"]:::step

    CONFIRM --> DECIDE{"Подтвердить создание?"}:::decision
    DECIDE -- "Изменить шаг" --> BACK["Открытие выбранного шага мастера"]:::aux
    BACK --> CONFIRM
    DECIDE -- "Подтвердить" --> SAVE["Создание поисковой сессии через employer-service"]:::step
    SAVE --> OPEN["Экран созданного поиска<br/>с кнопкой открытия сессии"]:::step

    classDef step fill:#eef3f8,stroke:#4f5b66,stroke-width:1.2px,color:#000000;
    classDef decision fill:#f6f1e8,stroke:#6b6255,stroke-width:1.2px,color:#000000;
    classDef aux fill:#f2f2f2,stroke:#666666,stroke-width:1.2px,color:#000000;
```
