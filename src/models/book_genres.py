import sqlalchemy as sa

from src.models.base import Base

book_genres = sa.Table(
    'book_genres',
    Base.metadata,
    sa.Column(
        'book_id',
        sa.Uuid,
        sa.ForeignKey('books.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
    sa.Column(
        'genre_id',
        sa.Uuid,
        sa.ForeignKey('genres.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
)
