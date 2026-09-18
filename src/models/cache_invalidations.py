from uuid import uuid7

import sqlalchemy as sa

from src.models.base import Base

cache_invalidations = sa.Table(
    'cache_invalidations',
    Base.metadata,
    sa.Column('id', sa.Uuid, primary_key=True, default=uuid7),
    sa.Column('key', sa.String(length=256), nullable=False),
    sa.Column(
        'created_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
)
