# backend/app/services/projection_grader.py
"""
Historical projection accuracy tracking and grading.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

logger = logging.getLogger(__name__)


def grade_yesterdays_projections(db: Session, target_date: Optional[date] = None):
    """
    Compare yesterday's projections to actual game results.
    
    Returns: Summary dict with games_graded, projections_graded
    """
    from app.models.player import Player, PlayerGameStats, Game
    from app.models.projections import ProjectionHistory, ProjectionResult
    
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    
    games = db.query(Game).filter(
        Game.date == target_date,
        Game.status == 'final',
        Game.home_score != None,
    ).all()
    
    if not games:
        logger.info(f"No completed games found for {target_date}")
        return {
            'date': str(target_date),
            'games_graded': 0,
            'projections_graded': 0,
        }
    
    logger.info(f"Grading projections for {len(games)} games on {target_date}")
    
    projections_graded = 0
    
    for game in games:
        stats = db.query(PlayerGameStats).filter(
            PlayerGameStats.game_id == game.id,
            PlayerGameStats.minutes >= 5,
        ).all()
        
        for stat in stats:
            projections = db.query(ProjectionHistory).filter(
                ProjectionHistory.player_id == stat.player_id,
                ProjectionHistory.game_id == game.id,
            ).all()
            
            for proj in projections:
                stat_type = proj.stat_type
                actual_value = _get_actual_stat(stat, stat_type)
                
                if actual_value is None:
                    continue
                
                error = actual_value - proj.projected_value
                abs_error = abs(error)
                pct_error = (error / actual_value * 100) if actual_value != 0 else 0
                
                bet_result = None
                over_hit = None
                under_hit = None
                
                if proj.line_value is not None:
                    if actual_value > proj.line_value:
                        over_hit = True
                        under_hit = False
                    elif actual_value < proj.line_value:
                        over_hit = False
                        under_hit = True
                    else:
                        over_hit = None
                        under_hit = None
                    
                    if proj.recommendation == 'OVER':
                        bet_result = 'win' if over_hit else ('push' if over_hit is None else 'loss')
                    elif proj.recommendation == 'UNDER':
                        bet_result = 'win' if under_hit else ('push' if under_hit is None else 'loss')
                
                result = ProjectionResult(
                    projection_id=proj.id,
                    player_id=stat.player_id,
                    game_id=game.id,
                    stat_type=stat_type,
                    projected_value=proj.projected_value,
                    actual_value=actual_value,
                    error=error,
                    abs_error=abs_error,
                    pct_error=pct_error,
                    line_value=proj.line_value,
                    over_hit=over_hit,
                    under_hit=under_hit,
                    recommendation=proj.recommendation,
                    bet_result=bet_result,
                    edge_pct=proj.edge_pct,
                )
                db.add(result)
                projections_graded += 1
    
    db.commit()
    
    logger.info(f"Graded {projections_graded} projections from {len(games)} games")
    
    return {
        'date': str(target_date),
        'games_graded': len(games),
        'projections_graded': projections_graded,
    }


def _get_actual_stat(stat: 'PlayerGameStats', stat_type: str) -> Optional[float]:
    """Extract actual stat value from game stats row."""
    stat_map = {
        'points': 'points',
        'rebounds': 'rebounds',
        'assists': 'assists',
        'steals': 'steals',
        'blocks': 'blocks',
        'pra': 'pra',
        'pr': 'pr',
        'pa': 'pa',
        'ra': 'ra',
    }
    
    col_name = stat_map.get(stat_type)
    if col_name:
        return getattr(stat, col_name, None)
    return None


def calculate_model_accuracy(
    db: Session,
    stat_type: str = 'points',
    days_back: int = 30,
    min_edge: Optional[float] = None,
) -> dict:
    """
    Calculate model accuracy metrics over a time period.
    
    Returns dict with overall accuracy, error metrics, by edge size, etc.
    """
    from app.models.projections import ProjectionResult
    from app.models.player import Game
    
    cutoff_date = date.today() - timedelta(days=days_back)
    
    query = db.query(ProjectionResult).join(
        Game, ProjectionResult.game_id == Game.id
    ).filter(
        ProjectionResult.stat_type == stat_type,
        Game.date >= cutoff_date,
        ProjectionResult.bet_result != None,
    )
    
    if min_edge is not None:
        query = query.filter(
            func.abs(ProjectionResult.edge_pct) >= min_edge
        )
    
    results = query.all()
    
    if not results:
        return {
            'stat_type': stat_type,
            'days_back': days_back,
            'sample_size': 0,
            'message': 'No graded projections found',
        }
    
    total = len(results)
    wins = sum(1 for r in results if r.bet_result == 'win')
    losses = sum(1 for r in results if r.bet_result == 'loss')
    pushes = sum(1 for r in results if r.bet_result == 'push')
    
    win_rate = (wins / (wins + losses)) if (wins + losses) > 0 else 0
    
    errors = [r.abs_error for r in results]
    mae = sum(errors) / len(errors)
    rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5
    
    # Profit at -110 odds, $100 per bet
    profit = (wins * 90.91) - (losses * 100)
    roi = (profit / (total * 100)) * 100
    
    # By edge bucket
    edge_buckets = {
        '3-5%': [],
        '5-10%': [],
        '10%+': [],
    }
    
    for r in results:
        abs_edge = abs(r.edge_pct or 0)
        if 3 <= abs_edge < 5:
            edge_buckets['3-5%'].append(r)
        elif 5 <= abs_edge < 10:
            edge_buckets['5-10%'].append(r)
        elif abs_edge >= 10:
            edge_buckets['10%+'].append(r)
    
    bucket_accuracy = {}
    for bucket, recs in edge_buckets.items():
        if recs:
            bucket_wins = sum(1 for r in recs if r.bet_result == 'win')
            bucket_total = sum(1 for r in recs if r.bet_result in ['win', 'loss'])
            bucket_accuracy[bucket] = {
                'win_rate': round((bucket_wins / bucket_total) * 100, 1) if bucket_total else 0,
                'sample_size': bucket_total,
            }
    
    # By recommendation
    over_recs = [r for r in results if r.recommendation == 'OVER']
    under_recs = [r for r in results if r.recommendation == 'UNDER']
    
    over_win_rate = 0
    under_win_rate = 0
    
    if over_recs:
        over_wins = sum(1 for r in over_recs if r.bet_result == 'win')
        over_total = sum(1 for r in over_recs if r.bet_result in ['win', 'loss'])
        over_win_rate = (over_wins / over_total * 100) if over_total else 0
    
    if under_recs:
        under_wins = sum(1 for r in under_recs if r.bet_result == 'win')
        under_total = sum(1 for r in under_recs if r.bet_result in ['win', 'loss'])
        under_win_rate = (under_wins / under_total * 100) if under_total else 0
    
    return {
        'stat_type': stat_type,
        'days_back': days_back,
        'min_edge_filter': min_edge,
        'sample_size': total,
        'overall': {
            'win_rate': round(win_rate * 100, 1),
            'wins': wins,
            'losses': losses,
            'pushes': pushes,
            'profit': round(profit, 2),
            'roi': round(roi, 1),
        },
        'error_metrics': {
            'mae': round(mae, 2),
            'rmse': round(rmse, 2),
        },
        'by_edge_size': bucket_accuracy,
        'by_recommendation': {
            'over_win_rate': round(over_win_rate, 1),
            'under_win_rate': round(under_win_rate, 1),
        },
    }