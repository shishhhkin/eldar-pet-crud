import pytest
from pydantic import BaseModel

from src.schemas.errors import (
    BodyValidationResponse,
    ConflictResponse,
    NotFoundResponse,
    PathValidationResponse,
)

ERROR_SCHEMAS = [
    NotFoundResponse,
    ConflictResponse,
    BodyValidationResponse,
    PathValidationResponse,
]


@pytest.mark.parametrize('schema', ERROR_SCHEMAS)
async def test_documented_example_validates_against_schema(schema: type[BaseModel]) -> None:
    examples = schema.model_json_schema().get('examples')

    assert examples
    for example in examples:
        schema.model_validate(example)
