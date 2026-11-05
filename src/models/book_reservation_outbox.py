import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from src.models.base import Base

book_reservation_outbox = sa.Table(
    'book_reservation_outbox',
    Base.metadata,
    sa.Column(
        'book_reservation_id',
        sa.Uuid,
        sa.ForeignKey('book_reservations.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
    ),
    sa.Column('payload', JSONB, nullable=False),
    sa.Column(
        'next_attempt_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    ),
    sa.Column('claim_token', sa.Uuid, server_default=sa.func.gen_random_uuid(), nullable=False),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        'created_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
)
