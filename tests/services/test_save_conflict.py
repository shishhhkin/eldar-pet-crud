import logging

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import GenreAlreadyExistsError, UserAlreadyExistsError
from src.models.genres import GenreModel
from src.repository import GenreRepo, Repo, UserRepo
from src.schemas.genres import GenreCreate
from src.schemas.moods import MoodPayload
from src.schemas.users import UserCreate, UserProfilePayload
from src.services.genre_service import GenreService
from src.services.user_service import UserService


def _genre_payload(name: str = 'нуар') -> GenreCreate:
    return GenreCreate(name=name, moods=[MoodPayload(name='грусть')])


def _user_payload(username: str = 'alice', email: str = 'alice@example.com') -> UserCreate:
    return UserCreate(username=username, email=email, profile=UserProfilePayload())


async def test_repo_save_propagates_raw_integrity_error(db_session: AsyncSession) -> None:
    repo = Repo(db_session, GenreModel)
    await repo.save(GenreModel(name='нуар'))

    with pytest.raises(IntegrityError):
        await repo.save(GenreModel(name='нуар'))


async def test_duplicate_genre_name_raises_already_exists(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = GenreService(GenreRepo(db_session))
    await service.create(_genre_payload())

    with (
        caplog.at_level(logging.INFO, logger='src.services.genre_service'),
        pytest.raises(GenreAlreadyExistsError) as excinfo,
    ):
        await service.create(_genre_payload())

    assert str(excinfo.value) == 'Genre already exists'
    records = [record for record in caplog.records if record.name == 'src.services.genre_service']
    assert records
    assert all(record.levelno == logging.INFO for record in records)
    assert any('нуар' in record.getMessage() for record in records)


async def test_duplicate_username_raises_already_exists(db_session: AsyncSession) -> None:
    service = UserService(UserRepo(db_session))
    await service.create(_user_payload())

    with pytest.raises(UserAlreadyExistsError) as excinfo:
        await service.create(_user_payload(email='other@example.com'))

    assert str(excinfo.value) == 'User already exists'


async def test_duplicate_email_raises_already_exists(db_session: AsyncSession) -> None:
    service = UserService(UserRepo(db_session))
    await service.create(_user_payload())

    with pytest.raises(UserAlreadyExistsError):
        await service.create(_user_payload(username='bob'))


async def test_repo_save_propagates_not_null_violation(db_session: AsyncSession) -> None:
    repo = Repo(db_session, GenreModel)

    with pytest.raises(IntegrityError):
        await repo.save(GenreModel())
