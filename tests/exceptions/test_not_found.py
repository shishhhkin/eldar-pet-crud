from uuid import uuid4

from src.exceptions import AuthorNotFoundError, ObjectNotFoundError


async def test_subclass_renders_default_template_with_entity() -> None:
    object_id = uuid4()

    assert AuthorNotFoundError(object_id).message == f'Author {object_id} not found'


async def test_message_template_override_changes_message() -> None:
    class WidgetNotFoundError(ObjectNotFoundError):
        entity = 'Widget'
        message_template = '{entity} {object_id} is gone'

    object_id = uuid4()

    assert WidgetNotFoundError(object_id).message == f'Widget {object_id} is gone'
