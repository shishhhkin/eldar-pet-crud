from collections.abc import Sequence

from src.mappers.base import apply_fields
from src.models.genres import GenreModel
from src.models.moods import MoodModel
from src.schemas.genres import GenreCreate, GenreUpdate


def to_genre_model(payload: GenreCreate, moods: Sequence[MoodModel]) -> GenreModel:
    return GenreModel(**payload.model_dump(exclude={'moods'}), moods=moods)


def apply_genre_update(
    genre: GenreModel, payload: GenreUpdate, moods: Sequence[MoodModel] | None
) -> None:
    apply_fields(genre, payload, exclude={'moods'})
    if moods is not None:
        genre.moods = list(moods)
