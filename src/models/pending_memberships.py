import sqlalchemy as sa

from src.models.base import Base

pending_memberships = sa.Table(
    'pending_memberships',
    Base.metadata,
    sa.Column(
        'user_id',
        sa.Uuid,
        sa.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
    sa.Column(
        'next_attempt_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    ),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        'created_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
)
