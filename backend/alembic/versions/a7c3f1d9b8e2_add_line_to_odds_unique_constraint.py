"""add line to odds unique constraint

Revision ID: a7c3f1d9b8e2
Revises: 1a610cd8504d
Create Date: 2026-02-23 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a7c3f1d9b8e2'
down_revision = '1a610cd8504d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('uq_odds_player_game_stat_book', 'odds_lines', type_='unique')
    op.create_unique_constraint(
        'uq_odds_player_game_stat_book_line',
        'odds_lines',
        ['player_id', 'game_id', 'stat_type', 'sportsbook', 'line'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_odds_player_game_stat_book_line', 'odds_lines', type_='unique')
    op.create_unique_constraint(
        'uq_odds_player_game_stat_book',
        'odds_lines',
        ['player_id', 'game_id', 'stat_type', 'sportsbook'],
    )
