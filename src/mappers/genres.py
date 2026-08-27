from src.mappers.base import apply_fields
from src.models.genres import GenreModel
from src.schemas.genres import GenreUpdate


def apply_genre_update(genre: GenreModel, payload: GenreUpdate) -> None:
    apply_fields(genre, payload, exclude={'moods'})
