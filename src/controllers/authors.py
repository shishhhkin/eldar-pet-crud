from uuid import UUID

from fastapi import APIRouter, Response, status

from src.db import SessionDep, TxSessionDep
from src.schemas.authors import AuthorCreate, AuthorRead, AuthorUpdate
from src.services import author_service

router = APIRouter(prefix='/authors', tags=['authors'])


# path нельзя убирать :(
@router.post('', response_model=AuthorRead, status_code=status.HTTP_201_CREATED)
async def create_author(payload: AuthorCreate, session: TxSessionDep) -> AuthorRead:
    return await author_service.create_author(session, payload)  # type: ignore[return-value]


@router.get('/{author_id}', response_model=AuthorRead)
async def read_author(author_id: UUID, session: SessionDep) -> AuthorRead:
    return await author_service.get_author(session, author_id)  # type: ignore[return-value]


@router.put('/{author_id}', response_model=AuthorRead)
async def update_author(
    author_id: UUID, payload: AuthorUpdate, session: TxSessionDep
) -> AuthorRead:
    return await author_service.update_author(session, author_id, payload)  # type: ignore[return-value]


@router.delete('/{author_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_author(author_id: UUID, session: TxSessionDep) -> Response:
    await author_service.delete_author(session, author_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
