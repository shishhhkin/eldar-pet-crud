import logging
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import NotFoundError
from src.infra.cache import Cache
from src.repository import AuthorRepo, GenreRepo, UserRepo
from src.services.author_service import AuthorService
from src.services.genre_service import GenreService
from src.services.user_service import UserService

LOGGER_NAME = 'src.services.base'

CASES = [
    (AuthorService, AuthorRepo, 'Author'),
    (GenreService, GenreRepo, 'Genre'),
    (UserService, UserRepo, 'User'),
]


@pytest.mark.parametrize(('service_cls', 'repo_cls', 'entity'), CASES)
async def test_get_missing_raises_not_found_and_logs(
    db_session: AsyncSession,
    cache: Cache,
    caplog: pytest.LogCaptureFixture,
    service_cls: type,
    repo_cls: type,
    entity: str,
) -> None:
    service = service_cls(repo_cls(db_session), cache)
    missing_id = uuid4()

    with (
        caplog.at_level(logging.INFO, logger=LOGGER_NAME),
        pytest.raises(NotFoundError) as excinfo,
    ):
        await service.get(missing_id)

    assert str(excinfo.value) == f'{entity} {missing_id} not found'

    records = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert records
    assert all(record.levelno == logging.INFO for record in records)
    assert any(str(missing_id) in record.getMessage() for record in records)
