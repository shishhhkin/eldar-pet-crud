from uuid import UUID

from src.exceptions.base import ValidationAppError


class GenresNotFound(ValidationAppError):
    def __init__(self, missing: list[UUID] | list[str]) -> None:
        super().__init__(f'genres not found: {[str(x) for x in missing]}')
