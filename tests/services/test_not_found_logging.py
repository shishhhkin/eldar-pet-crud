import logging
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AuthorNotFoundError, GenreNotFoundError, UserNotFoundError
from src.repository import AuthorRepo, GenreRepo, UserRepo
from src.services.author_service import AuthorService
from src.services.genre_service import GenreService
from src.services.user_service import UserService

CASES = [
    (AuthorService, AuthorRepo, AuthorNotFoundError, 'src.services.author_service'),
    (GenreService, GenreRepo, GenreNotFoundError, 'src.services.genre_service'),
    (UserService, UserRepo, UserNotFoundError, 'src.services.user_service'),
]


@pytest.mark.parametrize(('service_cls', 'repo_cls', 'error_cls', 'logger_name'), CASES)
async def test_get_missing_raises_entity_error_and_logs(
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    service_cls: type,
    repo_cls: type,
    error_cls: type[Exception],
    logger_name: str,
) -> None:
    service = service_cls(repo_cls(db_session))
    missing_id = uuid4()

    with caplog.at_level(logging.INFO, logger=logger_name), pytest.raises(error_cls):
        await service.get(missing_id)

    records = [record for record in caplog.records if record.name == logger_name]
    assert records
    assert all(record.levelno == logging.INFO for record in records)
    assert any(str(missing_id) in record.getMessage() for record in records)
