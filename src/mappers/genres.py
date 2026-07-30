from src.mappers.base import apply_fields
from src.models.genres import GenreModel
from src.schemas.genres import GenreRead, GenreUpdate


def apply_genre_update(genre: GenreModel, payload: GenreUpdate) -> None:
    apply_fields(genre, payload, exclude={'moods'})


def to_genre_read(genre: GenreModel) -> GenreRead:
    return GenreRead.model_validate(genre)
