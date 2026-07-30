from http import HTTPStatus

from src.exceptions import AlreadyExistsError, ConflictError


async def test_message_is_used_as_is() -> None:
    assert AlreadyExistsError('Genre already exists').message == 'Genre already exists'


async def test_falls_back_to_default_message() -> None:
    assert AlreadyExistsError().message == 'Already exists'
    assert ConflictError().message == 'Conflict'


async def test_keeps_conflict_status_and_code() -> None:
    error = AlreadyExistsError()

    assert error.status_code == HTTPStatus.CONFLICT
    assert error.code == 'already_exists'
