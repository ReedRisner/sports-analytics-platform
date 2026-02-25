"""add endpoint snapshots table

Revision ID: e8b1c2d3f4a5
Revises: d4b8c1e2f9aa
Create Date: 2026-02-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b1c2d3f4a5'
down_revision: Union[str, Sequence[str], None] = 'd4b8c1e2f9aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'endpoint_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=100), nullable=False),
        sa.Column('season', sa.String(length=10), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('opp_team_id', sa.Integer(), nullable=True),
        sa.Column('game_id', sa.Integer(), nullable=True),
        sa.Column('snapshot_date', sa.Date(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
        sa.ForeignKeyConstraint(['opp_team_id'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['player_id'], ['players.id'], ),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint', 'player_id', 'game_id', 'season', 'snapshot_date',
                            name='uq_endpoint_snapshots_endpoint_player_game_season_date')
    )
    op.create_index(op.f('ix_endpoint_snapshots_endpoint'), 'endpoint_snapshots', ['endpoint'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_game_id'), 'endpoint_snapshots', ['game_id'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_id'), 'endpoint_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_opp_team_id'), 'endpoint_snapshots', ['opp_team_id'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_player_id'), 'endpoint_snapshots', ['player_id'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_season'), 'endpoint_snapshots', ['season'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_snapshot_date'), 'endpoint_snapshots', ['snapshot_date'], unique=False)
    op.create_index(op.f('ix_endpoint_snapshots_team_id'), 'endpoint_snapshots', ['team_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_endpoint_snapshots_team_id'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_snapshot_date'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_season'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_player_id'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_opp_team_id'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_id'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_game_id'), table_name='endpoint_snapshots')
    op.drop_index(op.f('ix_endpoint_snapshots_endpoint'), table_name='endpoint_snapshots')
    op.drop_table('endpoint_snapshots')
