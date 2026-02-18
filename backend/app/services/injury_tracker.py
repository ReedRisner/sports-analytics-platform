# backend/app/services/injury_tracker.py
"""
NBA injury tracking and impact analysis.
Integrates with nbainjuries package.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from sqlalchemy import desc

logger = logging.getLogger(__name__)

# Try to import nbainjuries, but make it optional
INJURIES_AVAILABLE = False
injury = None

try:
    from nbainjuries import injury as injury_module
    injury = injury_module
    INJURIES_AVAILABLE = True
    logger.info("✓ nbainjuries package loaded successfully - injury tracking enabled")
except Exception as e:
    logger.warning(f"⚠ nbainjuries not available: {str(e)[:100]}")
    logger.warning("⚠ Injury tracking disabled - projections will work without it")


# ── CACHE for injury reports (so we don't spam the API) ──────────────────────
_injury_cache = {}
_cache_expiry = {}

def _get_cached_injuries(game_date: date) -> Optional[list]:
    """Check if we have a cached injury report for this date."""
    cache_key = str(game_date)
    
    # Check if cache exists and is still valid (expires after 1 hour)
    if cache_key in _injury_cache:
        expiry = _cache_expiry.get(cache_key)
        if expiry and datetime.now() < expiry:
            return _injury_cache[cache_key]
    
    return None

def _cache_injuries(game_date: date, injuries: list):
    """Store injury report in cache for 1 hour."""
    cache_key = str(game_date)
    _injury_cache[cache_key] = injuries
    _cache_expiry[cache_key] = datetime.now() + timedelta(hours=1)


def _normalize_name(name: str) -> str:
    """Normalize player name for fuzzy matching."""
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.lower().strip()


def _name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity ratio between two names."""
    return SequenceMatcher(None, _normalize_name(name1), _normalize_name(name2)).ratio()


def fetch_todays_injuries(game_date: Optional[date] = None) -> list:
    """
    Fetch NBA injury report for a specific date.
    
    Returns: List of injury records (empty if nbainjuries unavailable or report doesn't exist)
    """
    if not INJURIES_AVAILABLE or injury is None:
        return []
    
    if game_date is None:
        game_date = date.today()
    
    # Check cache first
    cached = _get_cached_injuries(game_date)
    if cached is not None:
        return cached
    
    try:
        # nbainjuries expects datetime, default to 5pm ET
        report_time = datetime(
            year=game_date.year,
            month=game_date.month,
            day=game_date.day,
            hour=17,
            minute=0
        )
        
        # Fetch as JSON (simpler than DataFrame)
        injury_data = injury.get_reportdata(report_time)
        
        if not injury_data:
            # Cache empty result to avoid repeated lookups
            _cache_injuries(game_date, [])
            return []
        
        # Cache successful result
        _cache_injuries(game_date, injury_data)
        logger.info(f"✓ Fetched {len(injury_data)} injury records for {game_date}")
        return injury_data
    
    except Exception as e:
        # Cache empty result on error (likely 403 - report doesn't exist yet)
        # This prevents spamming the API with repeated failed requests
        _cache_injuries(game_date, [])
        
        # Only log once per date to avoid spam
        if str(game_date) not in _injury_cache or len(_injury_cache) < 2:
            logger.debug(f"Injury report not available for {game_date}: {str(e)[:50]}")
        
        return []


def get_player_injury_status(
    db: Session,
    player_id: int,
    game_date: Optional[date] = None
) -> Optional[str]:
    """
    Check if a player is injured/out for a specific game.
    
    Returns: 'Out', 'Questionable', 'Doubtful', 'Available', or None
    """
    if not INJURIES_AVAILABLE:
        return None
    
    from app.models.player import Player, Team
    
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return None
    
    team = db.query(Team).filter(Team.id == player.team_id).first()
    if not team:
        return None
    
    injuries = fetch_todays_injuries(game_date)
    
    for inj in injuries:
        name_match = _name_similarity(player.name, inj.get('Player Name', '')) >= 0.85
        team_match = team.name in inj.get('Team', '') or team.abbreviation in inj.get('Team', '')
        
        if name_match and team_match:
            return inj.get('Current Status')
    
    return None


def calculate_injury_impact_factor(
    db: Session,
    player_id: int,
    game_date: Optional[date] = None,
) -> float:
    """
    Calculate usage boost when high-usage teammates are injured.
    
    Returns: 1.0 if injury tracking unavailable, otherwise calculated boost
    """
    if not INJURIES_AVAILABLE:
        # Return neutral factor - no injury data available
        return 1.0
    
    from app.models.player import Player, PlayerGameStats, Game
    
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return 1.0
    
    # Get player's recent average usage rate
    recent_games = (
        db.query(PlayerGameStats)
        .join(Game, PlayerGameStats.game_id == Game.id)
        .filter(
            PlayerGameStats.player_id == player_id,
            PlayerGameStats.minutes >= 15,
            PlayerGameStats.usage_rate != None,
        )
        .order_by(desc(Game.date))
        .limit(10)
        .all()
    )
    
    if not recent_games:
        return 1.0
    
    player_usage = sum(g.usage_rate for g in recent_games) / len(recent_games)
    
    # Get all active teammates
    teammates = (
        db.query(Player)
        .filter(
            Player.team_id == player.team_id,
            Player.id != player_id,
            Player.is_active == True,
        )
        .all()
    )
    
    # Use cached injury data
    injuries = fetch_todays_injuries(game_date)
    
    # If no injury data, return neutral (avoids spamming failed requests)
    if not injuries:
        return 1.0
    
    missing_usage = 0.0
    healthy_teammates = []
    
    for teammate in teammates:
        # Check injury status
        status = None
        for inj in injuries:
            if _name_similarity(teammate.name, inj.get('Player Name', '')) >= 0.85:
                status = inj.get('Current Status')
                break
        
        # Get teammate's average usage
        tm_games = (
            db.query(PlayerGameStats)
            .join(Game, PlayerGameStats.game_id == Game.id)
            .filter(
                PlayerGameStats.player_id == teammate.id,
                PlayerGameStats.minutes >= 15,
                PlayerGameStats.usage_rate != None,
            )
            .order_by(desc(Game.date))
            .limit(10)
            .all()
        )
        
        if not tm_games:
            continue
        
        tm_usage = sum(g.usage_rate for g in tm_games) / len(tm_games)
        
        if status in ['Out', 'Doubtful'] and tm_usage > 20.0:
            missing_usage += tm_usage
            logger.info(f"✓ {teammate.name} OUT ({tm_usage:.1f}% usage) - redistributing")
        else:
            healthy_teammates.append((teammate.id, tm_usage))
    
    if missing_usage == 0 or not healthy_teammates:
        return 1.0
    
    total_healthy_usage = sum(usg for _, usg in healthy_teammates)
    
    if total_healthy_usage == 0:
        return 1.0
    
    redistribution_share = (player_usage / total_healthy_usage) * missing_usage
    
    # 5% usage increase ≈ 8-10% stat increase
    usage_boost_factor = 1.0 + (redistribution_share / player_usage) * 0.85
    
    # Cap at +15%
    usage_boost_factor = min(1.15, usage_boost_factor)
    
    if usage_boost_factor > 1.02:
        logger.info(
            f"✓ {player.name} injury boost: {usage_boost_factor:.3f}x "
            f"({missing_usage:.1f}% missing usage)"
        )
    
    return usage_boost_factor