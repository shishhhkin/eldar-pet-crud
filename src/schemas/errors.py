from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

_REQUEST_ID_EXAMPLE = '8727204f-be85-4c38-acf4-455ed8188dc0'
_RESOURCE_ID_EXAMPLE = '22235be6-92c8-4eee-8a26-b6b05cc323ab'

_NOT_FOUND_DESC = 'Объект с указанным id не найден'
_CONFLICT_DESC = 'Конфликт: нарушение уникальности или ссылочной целостности'
_BODY_VALIDATION_DESC = 'Ошибка валидации тела запроса'
_PATH_VALIDATION_DESC = 'Некорректный формат id в пути'

_NOT_FOUND_EXAMPLE: dict[str, Any] = {
    'code': 'not_found',
    'detail': f'Resource {_RESOURCE_ID_EXAMPLE} not found',
    'request_id': _REQUEST_ID_EXAMPLE,
}
_CONFLICT_EXAMPLE: dict[str, Any] = {
    'code': 'conflict',
    'detail': 'Conflict: resource violates a uniqueness or relational constraint',
    'request_id': _REQUEST_ID_EXAMPLE,
}
_BODY_VALIDATION_EXAMPLE: dict[str, Any] = {
    'detail': [
        {
            'type': 'string_too_short',
            'loc': ['body', '<field>'],
            'msg': 'String should have at least 1 character',
            'input': '',
            'ctx': {'min_length': 1},
        },
    ],
}
_PATH_VALIDATION_EXAMPLE: dict[str, Any] = {
    'detail': [
        {
            'type': 'uuid_parsing',
            'loc': ['path', '<id>'],
            'msg': 'Input should be a valid UUID',
            'input': '<not-a-uuid>',
        },
    ],
}


class ErrorResponse(BaseModel):
    code: str
    detail: str
    request_id: str | None = None


class NotFoundResponse(ErrorResponse):
    model_config = ConfigDict(json_schema_extra={'examples': [_NOT_FOUND_EXAMPLE]})


class ConflictResponse(ErrorResponse):
    model_config = ConfigDict(json_schema_extra={'examples': [_CONFLICT_EXAMPLE]})


class ValidationErrorItem(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    input: Any = None
    ctx: dict[str, Any] | None = None


class BodyValidationResponse(BaseModel):
    detail: list[ValidationErrorItem]

    model_config = ConfigDict(json_schema_extra={'examples': [_BODY_VALIDATION_EXAMPLE]})


class PathValidationResponse(BaseModel):
    detail: list[ValidationErrorItem]

    model_config = ConfigDict(json_schema_extra={'examples': [_PATH_VALIDATION_EXAMPLE]})


CREATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    409: {'model': ConflictResponse, 'description': _CONFLICT_DESC},
    422: {'model': BodyValidationResponse, 'description': _BODY_VALIDATION_DESC},
}
READ_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {'model': NotFoundResponse, 'description': _NOT_FOUND_DESC},
    422: {'model': PathValidationResponse, 'description': _PATH_VALIDATION_DESC},
}
UPDATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {'model': NotFoundResponse, 'description': _NOT_FOUND_DESC},
    409: {'model': ConflictResponse, 'description': _CONFLICT_DESC},
    422: {'model': BodyValidationResponse, 'description': _BODY_VALIDATION_DESC},
}
DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {'model': NotFoundResponse, 'description': _NOT_FOUND_DESC},
    422: {'model': PathValidationResponse, 'description': _PATH_VALIDATION_DESC},
}
