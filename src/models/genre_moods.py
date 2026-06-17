import sqlalchemy as sa

from src.models.base import Base

genre_moods = sa.Table(
    'genre_moods',
    Base.metadata,
    sa.Column(
        'genre_id',
        sa.Uuid,
        sa.ForeignKey('genres.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
    sa.Column(
        'mood_id',
        sa.Uuid,
        sa.ForeignKey('moods.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
)
