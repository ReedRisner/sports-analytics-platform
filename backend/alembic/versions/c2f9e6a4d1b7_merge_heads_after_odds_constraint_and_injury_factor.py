"""merge heads after odds constraint and injury_factor

Revision ID: c2f9e6a4d1b7
Revises: 9f3c2d8a1b4e, a7c3f1d9b8e2
Create Date: 2026-02-23 10:00:00.000000
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'c2f9e6a4d1b7'
down_revision: Union[str, Sequence[str], None] = ('9f3c2d8a1b4e', 'a7c3f1d9b8e2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration - no schema changes.
    pass


def downgrade() -> None:
    # Merge migration - no schema changes.
    pass
