from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import SessionDep, TxSessionDep
from src.exceptions import ObjectNotFoundError
from src.models.authors import AuthorModel
from src.schemas.authors import AuthorCreate, AuthorUpdate


class AuthorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_books(self, author_id: UUID) -> AuthorModel | None:
        stmt = (
            select(AuthorModel)
            .where(AuthorModel.id == author_id)
            .options(selectinload(AuthorModel.books))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, payload: AuthorCreate) -> AuthorModel:
        author = AuthorModel(**payload.model_dump())
        self.session.add(author)
        await self.session.flush()
        await self.session.refresh(author, attribute_names=['books'])
        return author

    async def get(self, author_id: UUID) -> AuthorModel:
        author = await self._get_with_books(author_id)
        if author is None:
            raise ObjectNotFoundError(AuthorModel, author_id)
        return author

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorModel:
        author = await self._get_with_books(author_id)
        if author is None:
            raise ObjectNotFoundError(AuthorModel, author_id)
        for field, value in payload.model_dump().items():
            setattr(author, field, value)
        await self.session.flush()
        return author

    async def delete(self, author_id: UUID) -> None:
        author = await self.session.get(AuthorModel, author_id)
        if author is None:
            raise ObjectNotFoundError(AuthorModel, author_id)
        await self.session.delete(author)
        await self.session.flush()


def _author_service(session: SessionDep) -> AuthorService:
    return AuthorService(session)


def _author_service_tx(session: TxSessionDep) -> AuthorService:
    return AuthorService(session)


AuthorServiceDep = Annotated[AuthorService, Depends(_author_service)]
AuthorServiceTxDep = Annotated[AuthorService, Depends(_author_service_tx)]
