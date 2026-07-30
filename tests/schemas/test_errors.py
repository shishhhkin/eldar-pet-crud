import pytest
from pydantic import BaseModel

from src.exceptions import AlreadyExistsError, NotFoundError
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

DOCUMENTED_CODES = [
    (NotFoundResponse, NotFoundError.code),
    (ConflictResponse, AlreadyExistsError.code),
]


@pytest.mark.parametrize('schema', ERROR_SCHEMAS)
async def test_documented_example_validates_against_schema(schema: type[BaseModel]) -> None:
    examples = schema.model_json_schema().get('examples')

    assert examples
    for example in examples:
        schema.model_validate(example)


@pytest.mark.parametrize(('schema', 'code'), DOCUMENTED_CODES)
async def test_documented_example_uses_code_the_api_actually_returns(
    schema: type[BaseModel],
    code: str,
) -> None:
    examples = schema.model_json_schema()['examples']

    assert [example['code'] for example in examples] == [code]
