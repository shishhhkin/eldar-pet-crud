from src.mappers.base import apply_fields
from src.models.authors import AuthorModel
from src.models.books import BookModel
from src.schemas.authors import AuthorCreate, AuthorUpdate


def to_author_model(payload: AuthorCreate) -> AuthorModel:
    return AuthorModel(
        **payload.model_dump(exclude={'books'}),
        books=[BookModel(**book.model_dump()) for book in payload.books],
    )


def apply_author_update(author: AuthorModel, payload: AuthorUpdate) -> None:
    apply_fields(author, payload, exclude={'books'})
    if 'books' in payload.model_fields_set and payload.books is not None:
        author.books = [BookModel(**book.model_dump()) for book in payload.books]
