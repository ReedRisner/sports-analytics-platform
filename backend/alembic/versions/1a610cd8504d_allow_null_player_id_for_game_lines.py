"""allow null player_id for game lines

Revision ID: 1a610cd8504d
Revises: 31e1505ad7ee
Create Date: 2026-02-18 20:56:20.341670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a610cd8504d'
down_revision: Union[str, None] = '31e1505ad7ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column('odds_lines', 'player_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)

def downgrade():
    op.alter_column('odds_lines', 'player_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)