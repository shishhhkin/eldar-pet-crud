import logging
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.library import LibraryClient
from src.exceptions import NotFoundError
from src.infra.cache import Cache
from src.repository import (
    AuthorRepo,
    CacheInvalidationRepo,
    GenreRepo,
    MembershipRequestRepo,
    UserRepo,
)
from src.services.author_service import AuthorService
from src.services.base import BaseService
from src.services.genre_service import GenreService
from src.services.membership_issuer import MembershipIssuer
from src.services.user_service import UserService

LOGGER_NAME = 'src.services.base'


@pytest.fixture
def services(
    db_session: AsyncSession,
    cache: Cache,
    library: LibraryClient,
    membership_issuer: MembershipIssuer,
) -> dict[str, BaseService]:
    invalidations = CacheInvalidationRepo(db_session)
    return {
        'Author': AuthorService(AuthorRepo(db_session), invalidations, cache),
        'Genre': GenreService(GenreRepo(db_session), invalidations, cache),
        'User': UserService(
            UserRepo(db_session),
            invalidations,
            cache,
            library,
            membership_issuer,
            MembershipRequestRepo(db_session),
        ),
    }


@pytest.mark.parametrize('entity', ['Author', 'Genre', 'User'])
async def test_get_missing_raises_not_found_and_logs(
    services: dict[str, BaseService],
    caplog: pytest.LogCaptureFixture,
    entity: str,
) -> None:
    missing_id = uuid4()

    with (
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
        pytest.raises(NotFoundError) as excinfo,
    ):
        await services[entity].get(missing_id)

    assert str(excinfo.value) == f'{entity} {missing_id} not found'

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert records
    assert all(record.levelno == logging.INFO for record in records)
    assert any(str(missing_id) in record.getMessage() for record in records)
