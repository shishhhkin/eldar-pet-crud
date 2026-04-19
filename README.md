# eldar-pet-crud

Асинхронный CRUD-сервис на FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL.

## Сущности

- **User ↔ UserProfile** — 1:1
- **Author → Book** — 1:N
- **Book ↔ Genre** — M:N (через `book_genres`)

## Стек

- Python 3.14, FastAPI, Pydantic v2, SQLAlchemy (async) + asyncpg, Alembic
- pytest + pytest-asyncio, httpx (ASGI-транспорт)
- ruff
- Docker + docker-compose
- uv (менеджер зависимостей)

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

База `{postgres_db}_test` создаётся автоматически при первом запуске. Схема пересоздаётся перед каждым тестом. 48 тестов e2e через `httpx.AsyncClient` + `ASGITransport`.

## Апгрейд стартового шаблона

Перед основной работой шаблон был приведён к актуальным версиям FastAPI / Pydantic v2 / SQLAlchemy 2.0:

- **`src/application.py`:** убран `UJSONResponse` (deprecated) — Pydantic v2 сам сериализует в JSON; `CORSMiddleware` через канонический `fastapi.middleware.cors`; импорты от корня пакета `src.*`; добавлен `lifespan` вместо `on_event`.
- **`src/config.py`:** переход на `pydantic-settings` v2 — `model_config = SettingsConfigDict(...)` вместо вложенного `class Config`, удалён `Field(env=...)` (убран в v2), `pathlib.Path` вместо `os.path.*`.
- **`src/db.py`:** `get_session` переписан как обычный async-генератор под `Depends` (раньше — `@asynccontextmanager` с некорректной аннотацией); убран неявный `commit` на выходе из контекста — транзакциями управляет вызывающий код; добавлен `SessionDep = Annotated[AsyncSession, Depends(get_session)]`.
- **`src/main.py`:** убрана обёртка `asyncio.run(uvicorn.run(...))` (вложенные event loop'ы → `RuntimeError`), `uvicorn.run` вызывается напрямую; путь к фабрике — `src.application:get_app` (устойчив к CWD/reload).

## Структура

```
src/
  application.py   # FastAPI factory
  config.py        # Settings
  db.py            # engine, SessionFactory, get_session
  models/          # SQLAlchemy модели
  schemas/         # Pydantic-схемы
  services/        # бизнес-логика
  controllers/     # FastAPI-роутеры
alembic/           # миграции
tests/e2e/         # интеграционные тесты
```