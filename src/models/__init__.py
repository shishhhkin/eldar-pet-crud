# Единая точка импорта для alembic: импортируя пакет `src.models`, мы гарантируем,
# что все модели зарегистрировались в Base.metadata (иначе autogenerate их не увидит).
from src.models.authors import AuthorModel
from src.models.base import Base
from src.models.book_genres import book_genres
from src.models.books import BookModel
from src.models.genres import GenreModel
from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel

__all__ = [
    'AuthorModel',
    'Base',
    'BookModel',
    'GenreModel',
    'UserModel',
    'UserProfileModel',
    'book_genres',
]
