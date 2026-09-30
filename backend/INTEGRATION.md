# Серверная версия СКЗ

Реализованы Flask API в `server/app.py`, бизнес-правила в `server/domain.py`, фоновые задачи в `server/worker.py` и отдельный интерфейс `dist/server.html` / `server.js`. PostgreSQL-схема применяется `server/migrate.py` при первом запуске.

Рабочая версия запускается из корня проекта через Docker Compose. Полная инструкция: `deploy/README.md`. Секреты задаются только на сервере через `deploy/.env`, которого нет в комплекте.

Опубликованный сайт chatgpt.site продолжает использовать демонстрационные `index.html` и `app.js`. Сервер отдаёт только `server.html`, `server.js`, `server.css` и библиотеку Excel; демонстрационный переключатель ролей недоступен.

## Основные API

- `/api/auth/login`, `/api/auth/logout`, `/api/auth/change-password`, `/api/me` — авторизация и сессии.
- `/api/state`, `/api/dashboard`, `/api/requests`, `/api/requests/<id>` — данные с проверкой роли.
- `/api/requests/assign`, `/api/imports/preview`, `/api/imports/commit`, `/api/export` — назначения, импорт, выгрузка.
- `/api/users`, `/api/users/<id>`, `/api/users/<id>/reset-password` — пользователи.
- `/api/holidays`, `/api/templates`, `/api/templates/download`, `/api/audit`, `/api/notifications` — справочники и история.

Все изменяющие запросы требуют Origin, сессию и X-CSRF-Token. ФИО не используется как идентификатор. Архив не удаляется; журнал хранится с заявкой в той же БД.

До допуска к эксплуатации необходима приёмка на целевом PostgreSQL-сервере: контейнеры, миграция, HTTPS, восстановление копии и нагрузка 50 пользователей. См. `reports/server-release.md`.
