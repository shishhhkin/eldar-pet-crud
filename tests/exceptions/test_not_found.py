from http import HTTPStatus
from uuid import uuid4

from src.exceptions import NotFoundError


async def test_message_is_used_as_is() -> None:
    message = f'Author {uuid4()} not found'

    assert NotFoundError(message).message == message


async def test_falls_back_to_default_message() -> None:
    assert NotFoundError().message == 'Not found'


async def test_keeps_not_found_status_and_code() -> None:
    error = NotFoundError()

    assert error.status_code == HTTPStatus.NOT_FOUND
    assert error.code == 'not_found'
