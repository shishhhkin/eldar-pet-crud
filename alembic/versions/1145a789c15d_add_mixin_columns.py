"""add timestamp/soft-delete mixin columns

Revision ID: 1145a789c15d
Revises: 2eb1f151321e
Create Date: 2026-04-30 23:41:13.765199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1145a789c15d'
down_revision: Union[str, Sequence[str], None] = '2eb1f151321e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MIXIN_TABLES = ('authors', 'genres', 'books', 'user_profiles')


def upgrade() -> None:
    """Upgrade schema."""
    for table in MIXIN_TABLES:
        op.add_column(
            table,
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                'is_deleted',
                sa.Boolean(),
                server_default=sa.text('false'),
                nullable=False,
            ),
        )

    op.add_column(
        'users',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'is_deleted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'is_deleted')
    op.drop_column('users', 'updated_at')

    for table in MIXIN_TABLES:
        op.drop_column(table, 'is_deleted')
        op.drop_column(table, 'updated_at')
        op.drop_column(table, 'created_at')
