"""add line_type to odds lines

Revision ID: d4b8c1e2f9aa
Revises: c2f9e6a4d1b7
Create Date: 2026-02-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b8c1e2f9aa'
down_revision: Union[str, Sequence[str], None] = 'c2f9e6a4d1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('odds_lines', sa.Column('line_type', sa.String(length=20), nullable=True, server_default='normal'))
    op.execute("UPDATE odds_lines SET line_type = 'normal' WHERE line_type IS NULL")
    op.alter_column('odds_lines', 'line_type', nullable=False, server_default=None)


def downgrade() -> None:
    op.drop_column('odds_lines', 'line_type')
