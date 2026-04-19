from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.db import SessionDep
from src.schemas.authors import AuthorCreate, AuthorRead, AuthorUpdate
from src.services import author_service

router = APIRouter(prefix='/authors', tags=['authors'])


@router.post('', response_model=AuthorRead, status_code=status.HTTP_201_CREATED)
async def create_author(payload: AuthorCreate, session: SessionDep) -> AuthorRead:
    async with session.begin():
        author = await author_service.create_author(session, payload)
    return AuthorRead.model_validate(author)


@router.get('/{author_id}', response_model=AuthorRead)
async def read_author(author_id: UUID, session: SessionDep) -> AuthorRead:
    author = await author_service.get_author(session, author_id)
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Author not found')
    return AuthorRead.model_validate(author)


@router.put('/{author_id}', response_model=AuthorRead)
async def update_author(
    author_id: UUID, payload: AuthorUpdate, session: SessionDep
) -> AuthorRead:
    async with session.begin():
        author = await author_service.update_author(session, author_id, payload)
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Author not found')
    return AuthorRead.model_validate(author)


@router.delete('/{author_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_author(author_id: UUID, session: SessionDep) -> Response:
    async with session.begin():
        deleted = await author_service.delete_author(session, author_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Author not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
