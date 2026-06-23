from pydantic import BaseModel

from src.models.base import Base


def apply_fields(model: Base, payload: BaseModel, *, exclude: set[str]) -> None:
    for key, value in payload.model_dump(exclude_unset=True, exclude=exclude).items():
        setattr(model, key, value)
