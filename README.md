# eldar-pet-crud

Асинхронный CRUD-сервис на FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL.

## Сущности

Три независимые пары; CRUD ведётся по родительской сущности пары (`User`,
`Author`, `Genre`), дочерние передаются вложенным JSON — вторичные ключи в API
не показываются.

- **User ↔ UserProfile** — 1:1
- **Author → Book** — 1:N
- **Genre ↔ Mood** — M:N (через `genre_moods`)

Идентификаторы — UUIDv7. Роуты API смонтированы под префиксом `/v1`.

## Архитектура

- **Контроллеры** (`src/controllers/`) — тонкие FastAPI-роутеры, получают сервис через `Depends`.
- **Сервисы** (`src/services/`) — классы с бизнес-логикой; `AsyncSession` инжектится в конструктор. Каждый сервис экспортирует две DI-зависимости: `*ServiceDep` (сессия без транзакции, для чтения) и `*ServiceTxDep` (сессия в транзакции через `session.begin()`, для мутаций).
- **Обработка ошибок** — доменные `AppError` (`src/exceptions/`), `IntegrityError` и непойманные исключения преобразуются в единый JSON-ответ (`code`, `detail`, `request_id`).
- **Middleware** (`src/middleware.py`) — `RequestIDMiddleware` проставляет `X-Request-ID` и кладёт его в `contextvar`, `LoggingMiddleware` логирует метод, путь, статус и длительность каждого запроса.

## Запуск

### Через docker-compose

```bash
docker compose up --build
```

Миграции применяются на старте контейнера. API: http://localhost:8000/docs

### Локально

```bash
uv sync
# поднять postgres (например через docker compose up postgres)
uv run alembic upgrade head
uv run python -m src.main
```

## Конфигурация

Настройки читаются из `.env` через `pydantic-settings` (`postgres_user`, `postgres_password`, `postgres_host`, `postgres_port`, `postgres_db`). Строка подключения собирается в `Settings.postgres_url` как `computed_field`.

## Тесты

```bash
uv run pytest
```

PostgreSQL поднимается в одноразовом контейнере через `testcontainers` (`postgres:17-alpine`) — отдельная БД и `.env` не нужны, нужен только запущенный Docker. Схема пересоздаётся перед каждым тестом. Тесты e2e через `httpx.AsyncClient` + `ASGITransport`.

## Апгрейд стартового шаблона

Перед основной работой шаблон был приведён к актуальным версиям FastAPI / Pydantic v2 / SQLAlchemy 2.0:

- **`src/application.py`:** убран `UJSONResponse` (deprecated) — Pydantic v2 сам сериализует в JSON; `CORSMiddleware` через канонический `fastapi.middleware.cors`; импорты от корня пакета `src.*`; добавлен `lifespan` вместо `on_event`.
- **`src/config.py`:** переход на `pydantic-settings` v2 — `model_config = SettingsConfigDict(...)` вместо вложенного `class Config`, удалён `Field(env=...)` (убран в v2), `pathlib.Path` вместо `os.path.*`.
- **`src/db.py`:** `get_session` переписан как обычный async-генератор под `Depends` (раньше — `@asynccontextmanager` с некорректной аннотацией); убран неявный `commit` на выходе из контекста — транзакциями управляет вызывающий код; добавлен `SessionDep = Annotated[AsyncSession, Depends(get_session)]`.
- **`src/main.py`:** убрана обёртка `asyncio.run(uvicorn.run(...))` (вложенные event loop'ы → `RuntimeError`), `uvicorn.run` вызывается напрямую; путь к фабрике — `src.application:get_app` (устойчив к CWD/reload).