# --- Устаревший/неидиоматичный для FastAPI вариант ---
# from contextlib import asynccontextmanager
#
# from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
#
# from src.config import Settings
#
# settings = Settings()
#
# engine: AsyncEngine = create_async_engine(
#     str(settings.postgres_url),
#     pool_pre_ping=True,
# )
#
# SessionFactory = async_sessionmaker(
#     bind=engine,
#     class_=AsyncSession,
#     expire_on_commit=False,
# )
#
#
# @asynccontextmanager
# async def get_session() -> AsyncSession:
#     # Проблемы:
#     # 1) Аннотация возвращаемого типа неверна: @asynccontextmanager превращает
#     #    функцию в фабрику async-контекст-менеджера, а не в корутину AsyncSession.
#     # 2) Автокоммит на выходе из контекста — «магическое» поведение: часто приводит
#     #    к неожиданным коммитам; принято явно коммитить в сервисном слое (Unit of Work).
#     # 3) Для FastAPI идиоматичнее обычный async-генератор, который инжектится через Depends.
#     # 4) engine создаётся на import-time — мешает тестам и управлению жизненным циклом;
#     #    лучше создавать внутри lifespan и класть в app.state.
#     async with SessionFactory() as session:
#         try:
#             yield session
#             await session.commit()
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             await session.close()
# ------------------------------------------------------

# Актуальный подход:
# - engine/SessionFactory создаются как модульные синглтоны (ок для простого сервиса),
#   но в больших приложениях их лучше поднимать внутри lifespan и хранить в app.state.
# - get_session — обычный async-генератор для использования через FastAPI Depends.
# - Никакого неявного commit на выходе: транзакция управляется явно через
#   `async with session.begin():` в сервисе/репозитории или session.commit() в ручке.
#   Откат при исключении гарантирует `async with SessionFactory()` — он сам закроет сессию.
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import Settings

settings = Settings()  # type: ignore[call-arg]

engine: AsyncEngine = create_async_engine(
    str(settings.postgres_url),
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-dependency: выдаёт AsyncSession на время запроса.

    Транзакции — ответственность вызывающего кода
    (`async with session.begin(): ...` или явный `session.commit()`).
    """
    async with SessionFactory() as session:
        yield session


# Удобный алиас для аннотаций ручек: `session: SessionDep`.
SessionDep = Annotated[AsyncSession, Depends(get_session)]
