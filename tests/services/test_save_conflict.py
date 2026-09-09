import logging

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AlreadyExistsError
from src.infra.cache import CacheSession
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


@pytest.fixture
def genre_repo(db_session: AsyncSession) -> Repo[GenreModel]:
    return Repo(db_session, GenreModel)


@pytest.fixture
def genre_service(db_session: AsyncSession, cache_session: CacheSession) -> GenreService:
    return GenreService(GenreRepo(db_session), cache_session)


@pytest.fixture
def user_service(db_session: AsyncSession, cache_session: CacheSession) -> UserService:
    return UserService(UserRepo(db_session), cache_session)


async def test_repo_save_propagates_raw_integrity_error(genre_repo: Repo[GenreModel]) -> None:
    await genre_repo.save(GenreModel(name='нуар'))

    with pytest.raises(IntegrityError):
        await genre_repo.save(GenreModel(name='нуар'))


async def test_duplicate_genre_name_raises_already_exists(
    genre_service: GenreService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await genre_service.create(_genre_payload())

    with (
        caplog.at_level(logging.INFO, logger='src.services.genre_service'),
        pytest.raises(AlreadyExistsError) as excinfo,
    ):
        await genre_service.create(_genre_payload())

    assert str(excinfo.value) == 'Genre with this name already exists'
    records = [record for record in caplog.records if record.name == 'src.services.genre_service']
    assert records
    assert all(record.levelno == logging.INFO for record in records)
    assert any('нуар' in record.getMessage() for record in records)


async def test_duplicate_username_raises_already_exists(user_service: UserService) -> None:
    await user_service.create(_user_payload())

    with pytest.raises(AlreadyExistsError) as excinfo:
        await user_service.create(_user_payload(email='other@example.com'))

    assert str(excinfo.value) == 'User with this username or email already exists'


async def test_duplicate_email_raises_already_exists(user_service: UserService) -> None:
    await user_service.create(_user_payload())

    with pytest.raises(AlreadyExistsError) as excinfo:
        await user_service.create(_user_payload(username='bob'))

    assert str(excinfo.value) == 'User with this username or email already exists'


async def test_repo_save_propagates_not_null_violation(genre_repo: Repo[GenreModel]) -> None:
    with pytest.raises(IntegrityError):
        await genre_repo.save(GenreModel())
