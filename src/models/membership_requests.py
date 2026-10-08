import sqlalchemy as sa

from src.models.base import Base

membership_requests = sa.Table(
    'membership_requests',
    Base.metadata,
    sa.Column(
        'user_id',
        sa.Uuid,
        sa.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
    sa.Column('attempts', sa.Integer, server_default=sa.text('0'), nullable=False),
    sa.Column(
        'next_attempt_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    ),
    sa.Column(
        'created_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
)
