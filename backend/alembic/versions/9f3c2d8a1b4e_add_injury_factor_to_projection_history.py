"""add injury_factor to projection_history

Revision ID: 9f3c2d8a1b4e
Revises: 1a610cd8504d
Create Date: 2026-02-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f3c2d8a1b4e'
down_revision: Union[str, None] = '1a610cd8504d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projection_history', sa.Column('injury_factor', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('projection_history', 'injury_factor')
