from http import HTTPStatus

from src.exceptions import AlreadyExistsError, GenreAlreadyExistsError


async def test_subclass_renders_default_template_with_entity() -> None:
    assert GenreAlreadyExistsError().message == 'Genre already exists'


async def test_message_template_override_changes_message() -> None:
    class WidgetAlreadyExistsError(AlreadyExistsError):
        entity = 'Widget'
        message_template = '{entity} is already taken'

    assert WidgetAlreadyExistsError().message == 'Widget is already taken'


async def test_subclass_keeps_conflict_status_and_code() -> None:
    error = GenreAlreadyExistsError()

    assert error.status_code == HTTPStatus.CONFLICT
    assert error.code == 'already_exists'
