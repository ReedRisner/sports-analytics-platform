from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.player import PlayerGameStats, Game
from typing import Optional

def calculate_streak(
    db: Session,
    player_id: int,
    stat_type: str,
    line: float,
    limit: int = 10
) -> dict:
    """Calculate hit/miss streak for a player on a specific line."""
    
    # Map stat types to database columns
    stat_columns = {
        "points": "points",
        "rebounds": "rebounds", 
        "assists": "assists",
        "steals": "steals",
        "blocks": "blocks",
    }
    
    games = (
        db.query(PlayerGameStats, Game)
        .join(Game, PlayerGameStats.game_id == Game.id)
        .filter(PlayerGameStats.player_id == player_id)
        .order_by(desc(Game.date))
        .limit(limit)
        .all()
    )
    
    results = []
    for stat, game in games:
        if stat_type == "pra":
            value = (stat.points or 0) + (stat.rebounds or 0) + (stat.assists or 0)
        elif stat_type in stat_columns:
            value = getattr(stat, stat_columns[stat_type]) or 0
        else:
            continue
        results.append(value > line)
    
    if not results:
        return {
            "current_streak": 0,
            "streak_type": None,
            "last_n_games": [],
            "hit_rate": 0.0
        }
    
    # Calculate current streak
    current_streak = 0
    streak_type = "hit" if results[0] else "miss"
    
    for hit in results:
        if hit == results[0]:
            current_streak += 1
        else:
            break
    
    hit_rate = sum(results) / len(results)
    
    return {
        "current_streak": current_streak,
        "streak_type": streak_type,
        "last_n_games": results,
        "hit_rate": round(hit_rate, 3)
    }