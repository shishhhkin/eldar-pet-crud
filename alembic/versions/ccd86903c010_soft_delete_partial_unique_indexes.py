"""soft delete: partial unique indexes for natural-key reuse

Revision ID: ccd86903c010
Revises: 1145a789c15d
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccd86903c010'
down_revision: Union[str, Sequence[str], None] = '1145a789c15d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TARGETS = (
    ('users', 'uq_users_username', 'username'),
    ('users', 'uq_users_email', 'email'),
    ('genres', 'uq_genres_name', 'name'),
)


def upgrade() -> None:
    """Upgrade schema."""
    for table, constraint, column in TARGETS:
        op.drop_constraint(constraint, table, type_='unique')
        op.create_index(
            f'uq_{table}_{column}_active',
            table,
            [column],
            unique=True,
            postgresql_where=sa.text('is_deleted = false'),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, constraint, column in TARGETS:
        op.drop_index(f'uq_{table}_{column}_active', table_name=table)
        op.create_unique_constraint(constraint, table, [column])
