# backend/app/services/projection_grader.py
"""
Historical projection accuracy tracking and grading.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.services.schema_compat import ensure_projection_history_schema

logger = logging.getLogger(__name__)


def _normalize_accuracy_stat_type(stat_type: str) -> str:
    """Normalize frontend/backfill aliases to canonical stat keys."""
    normalized = (stat_type or '').strip().lower()
    alias_map = {
        '3pm': 'threes',
        '3pt': 'threes',
        '3ptm': 'threes',
        'three_pointers_made': 'threes',
        'r+a': 'ra',
    }
    return alias_map.get(normalized, normalized)


def _stat_type_variants(stat_type: str) -> list[str]:
    normalized = _normalize_accuracy_stat_type(stat_type)
    variants = {normalized}
    if normalized == 'threes':
        variants.update({'3pm', '3pt', '3ptm', 'three_pointers_made'})
    if normalized == 'ra':
        variants.add('r+a')
    return list(variants)


def _to_probability(odds: Optional[int]) -> Optional[float]:
    if odds is None:
        return None
    if odds >= 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def _recommended_no_vig_probability(over_odds: Optional[int], under_odds: Optional[int], recommendation: Optional[str]) -> Optional[float]:
    over_prob = _to_probability(over_odds)
    under_prob = _to_probability(under_odds)
    if over_prob is None or under_prob is None:
        return None

    total = over_prob + under_prob
    if total <= 0:
        return None

    fair_over = over_prob / total
    fair_under = under_prob / total

    if recommendation == 'OVER':
        return round(fair_over, 4)
    if recommendation == 'UNDER':
        return round(fair_under, 4)
    return None


def grade_yesterdays_projections(db: Session, target_date: Optional[date] = None):
    """
    Compare yesterday's projections to actual game results.
    
    Returns: Summary dict with games_graded, projections_graded
    """
    from app.models.player import Player, PlayerGameStats, Game
    from app.models.projections import ProjectionHistory, ProjectionResult

    ensure_projection_history_schema(db)
    
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
    normalized_stat_type = _normalize_accuracy_stat_type(stat_type)

    stat_map = {
        'points': 'points',
        'rebounds': 'rebounds',
        'assists': 'assists',
        'steals': 'steals',
        'blocks': 'blocks',
        'threes': 'fg3m',
        'pra': 'pra',
        'pr': 'pr',
        'pa': 'pa',
        'ra': 'ra',
    }
    
    col_name = stat_map.get(normalized_stat_type)
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
    from app.models.projections import ProjectionResult, ProjectionHistory
    from app.models.player import Game, Player, Team, OddsLine
    
    normalized_stat_type = _normalize_accuracy_stat_type(stat_type)
    cutoff_date = date.today() - timedelta(days=days_back)
    
    stat_variants = _stat_type_variants(normalized_stat_type)

    query = db.query(ProjectionResult).join(
        Game, ProjectionResult.game_id == Game.id
    ).filter(
        ProjectionResult.stat_type.in_(stat_variants),
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
            'stat_type': normalized_stat_type,
            'days_back': days_back,
            'sample_size': 0,
            'top_edge_bets': [],
            'top_streaky_bets': [],
            'top_no_vig_bets': [],
            'message': 'No graded projections found',
        }

    detailed_rows = db.query(
        ProjectionResult,
        Game,
        Player,
        Team,
        ProjectionHistory,
        OddsLine,
    ).join(
        Game, ProjectionResult.game_id == Game.id
    ).join(
        Player, ProjectionResult.player_id == Player.id
    ).outerjoin(
        Team, Player.team_id == Team.id
    ).outerjoin(
        ProjectionHistory, ProjectionHistory.id == ProjectionResult.projection_id
    ).outerjoin(
        OddsLine,
        (OddsLine.player_id == ProjectionResult.player_id) &
        (OddsLine.game_id == ProjectionResult.game_id) &
        (OddsLine.stat_type == ProjectionResult.stat_type) &
        (OddsLine.line == ProjectionResult.line_value)
    ).filter(
        ProjectionResult.stat_type.in_(stat_variants),
        Game.date >= cutoff_date,
        ProjectionResult.bet_result != None,
    )

    if min_edge is not None:
        detailed_rows = detailed_rows.filter(func.abs(ProjectionResult.edge_pct) >= min_edge)

    detailed_rows = detailed_rows.all()

    def _base_bet_payload(row):
        result, game, player, team, history, odds_line = row
        no_vig_prob = _recommended_no_vig_probability(
            odds_line.over_odds if odds_line else None,
            odds_line.under_odds if odds_line else None,
            result.recommendation,
        )
        return {
            'player_id': result.player_id,
            'player_name': player.name if player else 'Unknown',
            'team_abbr': team.abbreviation if team and team.abbreviation else '?',
            'game_date': str(game.date),
            'stat_type': result.stat_type,
            'recommendation': result.recommendation,
            'bet_result': result.bet_result,
            'line': result.line_value,
            'projected': result.projected_value,
            'actual': result.actual_value,
            'edge_pct': round(result.edge_pct or 0, 2),
            'over_prob': round(history.over_prob, 4) if history and history.over_prob is not None else None,
            'under_prob': round(history.under_prob, 4) if history and history.under_prob is not None else None,
            'no_vig_prob': no_vig_prob,
        }

    top_edge_bets = [
        _base_bet_payload(row)
        for row in sorted(detailed_rows, key=lambda row: abs((row[0].edge_pct or 0)), reverse=True)[:10]
    ]

    streak_groups = {}
    ordered_rows = sorted(detailed_rows, key=lambda row: (row[1].date, row[0].id))
    for row in ordered_rows:
        result = row[0]
        key = (result.player_id, result.stat_type, result.recommendation)
        group = streak_groups.get(key)
        if not group:
            streak_groups[key] = {
                'current': 1,
                'last_result': result.bet_result,
                'latest_row': row,
            }
            continue

        if result.bet_result == group['last_result']:
            group['current'] += 1
        else:
            group['current'] = 1
            group['last_result'] = result.bet_result
        group['latest_row'] = row

    top_streaky_bets = []
    for group in streak_groups.values():
        payload = _base_bet_payload(group['latest_row'])
        payload['streak_count'] = group['current']
        payload['streak_type'] = group['last_result']
        top_streaky_bets.append(payload)

    top_streaky_bets.sort(key=lambda bet: bet['streak_count'], reverse=True)
    top_streaky_bets = top_streaky_bets[:10]

    top_no_vig_bets = [
        _base_bet_payload(row)
        for row in sorted(
            detailed_rows,
            key=lambda row: (_recommended_no_vig_probability(
                row[5].over_odds if row[5] else None,
                row[5].under_odds if row[5] else None,
                row[0].recommendation,
            ) or 0),
            reverse=True,
        )
        if _recommended_no_vig_probability(
            row[5].over_odds if row[5] else None,
            row[5].under_odds if row[5] else None,
            row[0].recommendation,
        ) is not None
    ][:10]
    
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
        'stat_type': normalized_stat_type,
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
        'top_edge_bets': top_edge_bets,
        'top_streaky_bets': top_streaky_bets,
        'top_no_vig_bets': top_no_vig_bets,
    }
