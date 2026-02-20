# backend/app/services/projection_saver.py
"""
Save projections to database for later grading.
"""

from sqlalchemy.orm import Session
from app.models.projections import ProjectionHistory
from app.services.projection_engine import Projection
from app.services.schema_compat import ensure_projection_history_schema


def save_projection(
    db: Session,
    proj: Projection,
    game_id: int,
    opp_team_id: int,
    line: float = None,
    sportsbook: str = None
):
    """
    Store a projection in the database for accuracy tracking.
    
    Call this whenever user views a projection or edge finder runs.
    """
    ensure_projection_history_schema(db)

    existing = db.query(ProjectionHistory).filter(
        ProjectionHistory.player_id == proj.player_id,
        ProjectionHistory.game_id == game_id,
        ProjectionHistory.stat_type == proj.stat_type,
    ).first()
    
    if existing:
        if line and existing.line_value != line:
            existing.line_value = line
            existing.edge_pct = proj.edge_pct
            existing.over_prob = proj.over_prob
            existing.under_prob = proj.under_prob
            existing.recommendation = proj.recommendation
            db.commit()
        return existing
    
    history = ProjectionHistory(
        player_id=proj.player_id,
        game_id=game_id,
        stat_type=proj.stat_type,
        projected_value=proj.projected,
        season_avg=proj.season_avg,
        l5_avg=proj.l5_avg,
        l10_avg=proj.l10_avg,
        std_dev=proj.std_dev,
        floor=proj.floor,
        ceiling=proj.ceiling,
        opp_team_id=opp_team_id,
        pace_factor=proj.matchup.pace_factor if proj.matchup else None,
        matchup_factor=proj.matchup.matchup_factor if proj.matchup else None,
        home_factor=proj.home_factor,
        rest_factor=proj.rest_factor,
        blowout_factor=proj.blowout_factor,
        injury_factor=proj.injury_factor,
        line_value=line,
        sportsbook=sportsbook,
        edge_pct=proj.edge_pct,
        over_prob=proj.over_prob,
        under_prob=proj.under_prob,
        recommendation=proj.recommendation,
    )
    
    db.add(history)
    db.commit()
    
    return history