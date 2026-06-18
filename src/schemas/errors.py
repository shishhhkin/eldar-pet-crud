from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    'ErrorResponse',
    'CREATE_RESPONSES',
    'READ_RESPONSES',
    'UPDATE_RESPONSES',
    'DELETE_RESPONSES',
]

_REQUEST_ID_EXAMPLE = '8727204f-be85-4c38-acf4-455ed8188dc0'
_RESOURCE_ID_EXAMPLE = '22235be6-92c8-4eee-8a26-b6b05cc323ab'


class ErrorResponse(BaseModel):
    code: str = Field(examples=['not_found'])
    detail: str = Field(examples=[f'Resource {_RESOURCE_ID_EXAMPLE} not found'])
    request_id: str | None = Field(default=None, examples=[_REQUEST_ID_EXAMPLE])


def _resp(code: str, description: str, detail: str) -> dict[str, Any]:
    return {
        'model': ErrorResponse,
        'description': description,
        'content': {
            'application/json': {
                'example': {
                    'code': code,
                    'detail': detail,
                    'request_id': _REQUEST_ID_EXAMPLE,
                },
            },
        },
    }


_NOT_FOUND = _resp(
    'not_found',
    'Объект с указанным id не найден',
    f'Resource {_RESOURCE_ID_EXAMPLE} not found',
)
_CONFLICT = _resp(
    'conflict',
    'Конфликт: нарушение уникальности или ссылочной целостности',
    'Conflict: resource violates a uniqueness or relational constraint',
)
_VALIDATION = {
    'description': 'Ошибка валидации тела запроса',
    'content': {
        'application/json': {
            'schema': {'$ref': '#/components/schemas/HTTPValidationError'},
            'example': {
                'detail': [
                    {
                        'type': 'string_too_short',
                        'loc': ['body', '<field>'],
                        'msg': 'String should have at least 1 character',
                        'input': '',
                        'ctx': {'min_length': 1},
                    },
                ],
            },
        },
    },
}

_PATH_VALIDATION = {
    'description': 'Некорректный формат id в пути',
    'content': {
        'application/json': {
            'schema': {'$ref': '#/components/schemas/HTTPValidationError'},
            'example': {
                'detail': [
                    {
                        'type': 'uuid_parsing',
                        'loc': ['path', '<id>'],
                        'msg': 'Input should be a valid UUID',
                        'input': '<not-a-uuid>',
                    },
                ],
            },
        },
    },
}

CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {409: _CONFLICT, 422: _VALIDATION}
READ_RESPONSES: dict[int | str, dict[str, Any]] = {404: _NOT_FOUND, 422: _PATH_VALIDATION}
UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: _NOT_FOUND,
    409: _CONFLICT,
    422: _VALIDATION,
}
DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {404: _NOT_FOUND, 422: _PATH_VALIDATION}
