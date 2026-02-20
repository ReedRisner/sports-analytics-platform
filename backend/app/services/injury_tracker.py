# backend/app/services/injury_tracker.py
"""
NBA injury tracking and impact analysis.
Integrates with nbainjuries package.
"""

import logging
import re
from datetime import datetime, date, timedelta
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

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
_player_usage_cache = {}
_team_usage_cache = {}


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


def _get_cached_usage(cache: dict, key: str):
    entry = cache.get(key)
    if not entry:
        return None
    expires_at = entry.get("expires_at")
    if not expires_at or datetime.now() >= expires_at:
        cache.pop(key, None)
        return None
    return entry.get("data")


def _set_cached_usage(cache: dict, key: str, data, ttl_minutes: int = 30):
    cache[key] = {
        "data": data,
        "expires_at": datetime.now() + timedelta(minutes=ttl_minutes),
    }


def _normalize_name(name: str) -> str:
    """Normalize player name for fuzzy matching."""
    import unicodedata

    name = unicodedata.normalize("NFKD", str(name or ""))
    name = "".join(c for c in name if not unicodedata.combining(c)).strip().lower()

    # Convert "last, first" -> "first last"
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            name = f"{parts[1]} {parts[0]}"

    # Remove punctuation/noise and common suffixes
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    tokens = [t for t in name.split() if t not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return " ".join(tokens)


def _name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity ratio between two names."""
    return SequenceMatcher(None, _normalize_name(name1), _normalize_name(name2)).ratio()


def _find_status_for_player(player_name: str, injuries: list) -> Optional[str]:
    """Find injury status for a player, handling name-order mismatches."""
    normalized_target = _normalize_name(player_name)
    if not normalized_target:
        return None

    best_status = None
    best_score = 0.0

    for inj in injuries:
        if not isinstance(inj, dict):
            continue

        injury_name = inj.get("Player Name", "")
        status = inj.get("Current Status")
        if not injury_name or not status:
            continue

        score = _name_similarity(normalized_target, injury_name)
        if score > best_score:
            best_score = score
            best_status = status

    return best_status if best_score >= 0.85 else None


def _team_matches_injury_record(team_name: str, team_abbreviation: str, injury_record: dict) -> bool:
    """Check whether an injury record likely belongs to the provided NBA team."""
    team_field = str(injury_record.get("Team", "") or "").strip().lower()
    if not team_field:
        return False

    normalized_name = str(team_name or "").strip().lower()
    normalized_abbr = str(team_abbreviation or "").strip().lower()

    return (
        (normalized_name and normalized_name in team_field)
        or (normalized_abbr and normalized_abbr in team_field)
    )


def _find_status_for_player_and_team(
    player_name: str,
    team_name: str,
    team_abbreviation: str,
    injuries: list,
) -> Optional[str]:
    """
    Find injury status for a player while preferring records that match the team.

    This prevents false negatives/positives when name matching is ambiguous.
    """
    normalized_target = _normalize_name(player_name)
    if not normalized_target:
        return None

    best_any_status = None
    best_any_score = 0.0
    best_team_status = None
    best_team_score = 0.0

    for inj in injuries:
        if not isinstance(inj, dict):
            continue

        injury_name = inj.get("Player Name", "")
        status = inj.get("Current Status")
        if not injury_name or not status:
            continue

        score = _name_similarity(normalized_target, injury_name)
        if score > best_any_score:
            best_any_score = score
            best_any_status = status

        if _team_matches_injury_record(team_name, team_abbreviation, inj) and score > best_team_score:
            best_team_score = score
            best_team_status = status

    if best_team_score >= 0.85:
        return best_team_status
    if best_any_score >= 0.85:
        return best_any_status
    return None


def _filter_injuries_for_team(team_name: str, team_abbreviation: str, injuries: list) -> list:
    """Return only injury feed rows that appear to belong to the provided team."""
    if not injuries:
        return []
    return [
        inj for inj in injuries
        if isinstance(inj, dict) and _team_matches_injury_record(team_name, team_abbreviation, inj)
    ]


def _status_indicates_unavailable(status: Optional[str]) -> bool:
    """Return True when a feed status should count as an inactive player."""
    normalized = str(status or "").strip().lower()
    if not normalized:
        return False

    # Covers values like "Out", "Out For Season", "DOUBTFUL", "Inactive".
    unavailable_keywords = ("out", "doubt", "inactive", "suspended", "g league")
    if any(keyword in normalized for keyword in unavailable_keywords):
        return True

    # Explicitly don't count game-time/availability statuses.
    available_keywords = ("questionable", "probable", "available", "active")
    return not any(keyword in normalized for keyword in available_keywords)


def fetch_todays_injuries(game_date: Optional[date] = None) -> list:
    """
    Fetch NBA injury report for a specific date.

    Tries multiple release windows because reports may publish at different times
    (including midnight) and some snapshots can fail validation.

    Returns: List of injury records (empty if unavailable)
    """
    if not INJURIES_AVAILABLE or injury is None:
        return []

    if game_date is None:
        game_date = date.today()

    # Check cache first
    cached = _get_cached_injuries(game_date)
    if cached is not None:
        return cached

    candidate_times = [
        # User-observed early release
        datetime(game_date.year, game_date.month, game_date.day, 0, 0),
        # Midday update window
        datetime(game_date.year, game_date.month, game_date.day, 12, 0),
        # Traditional evening report window
        datetime(game_date.year, game_date.month, game_date.day, 17, 0),
        # Fallback to prior evening report if today's snapshots are unavailable
        datetime.combine(game_date - timedelta(days=1), datetime.min.time()).replace(hour=17),
    ]

    last_error = None
    for report_time in candidate_times:
        try:
            injury_data = injury.get_reportdata(report_time)
            if injury_data:
                _cache_injuries(game_date, injury_data)
                logger.info(
                    f"✓ Fetched {len(injury_data)} injury records for {game_date} "
                    f"(snapshot {report_time:%Y-%m-%d %I:%M%p})"
                )
                return injury_data
        except Exception as e:
            last_error = e
            continue

    # Cache empty result to avoid repeated failing lookups for the same date.
    _cache_injuries(game_date, [])
    if last_error is not None:
        logger.debug(
            f"Injury report not available for {game_date}; "
            f"tried midnight/noon/5pm snapshots ({str(last_error)[:80]})"
        )
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
    team_injuries = _filter_injuries_for_team(team.name, team.abbreviation, injuries)

    status = _find_status_for_player_and_team(
        player_name=player.name,
        team_name=team.name,
        team_abbreviation=team.abbreviation,
        injuries=team_injuries or injuries,
    )
    if not status:
        return None

    # Keep loose team check as a sanity filter when team field is present.
    for inj in (team_injuries or injuries):
        if not isinstance(inj, dict):
            continue
        if _name_similarity(player.name, inj.get("Player Name", "")) < 0.85:
            continue
        team_field = str(inj.get("Team", ""))
        if not team_field or team.name in team_field or team.abbreviation in team_field:
            return status

    return status


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

    from app.models.player import Player, PlayerGameStats, Game, Team

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return 1.0

    team = db.query(Team).filter(Team.id == player.team_id).first()
    if not team:
        return 1.0

    cache_date = game_date or date.today()
    usage_cache_key = f"{cache_date}:{player_id}"

    # Get player's recent usage/minutes context (cached)
    player_context = _get_cached_usage(_player_usage_cache, usage_cache_key)
    player_usage = None
    player_minutes = None

    if isinstance(player_context, dict):
        player_usage = player_context.get("usage")
        player_minutes = player_context.get("minutes")
    elif isinstance(player_context, (int, float)):
        # Backward compatibility for prior cache format.
        player_usage = float(player_context)

    if player_usage is None or player_minutes is None:
        recent_games = (
            db.query(PlayerGameStats)
            .join(Game, PlayerGameStats.game_id == Game.id)
            .filter(
                PlayerGameStats.player_id == player_id,
                PlayerGameStats.minutes >= 15,
                PlayerGameStats.usage_rate.isnot(None),
            )
            .order_by(desc(Game.date))
            .limit(10)
            .all()
        )

        if not recent_games:
            return 1.0

        player_usage = sum(g.usage_rate for g in recent_games) / len(recent_games)
        player_minutes = sum(g.minutes for g in recent_games) / len(recent_games)
        _set_cached_usage(
            _player_usage_cache,
            usage_cache_key,
            {"usage": player_usage, "minutes": player_minutes},
        )

    # Weight by role: players with bigger minute loads absorb more vacated usage.
    player_minutes_weight = max(0.4, min(1.3, (player_minutes or 24.0) / 30.0))

    # Get all active teammates
    teammates = (
        db.query(Player)
        .filter(
            Player.team_id == player.team_id,
            Player.id != player_id,
            Player.is_active.is_(True),
        )
        .all()
    )

    # Use cached injury data
    injuries = fetch_todays_injuries(game_date)
    team_injuries = _filter_injuries_for_team(team.name, team.abbreviation, injuries)

    # Fallback: when external injury feed is unavailable/invalid, infer likely
    # absences from most recent completed team game so injury factor still works.
    inferred_out_ids = set()
    if not team_injuries:
        inferred_out_ids = _infer_recent_absent_teammates(
            db=db,
            team_id=player.team_id,
            game_date=cache_date,
        )

    # If no injury data and no inferred absences, return neutral.
    if not team_injuries and not inferred_out_ids:
        return 1.0

    # Keep raw injuries list; lookup handles first/last vs last,first formats.
    team_usage_cache_key = f"{cache_date}:{player.team_id}"
    team_context_map = _get_cached_usage(_team_usage_cache, team_usage_cache_key)
    if team_context_map is None:
        team_context_map = {}
        for teammate in teammates:
            tm_games = (
                db.query(PlayerGameStats)
                .join(Game, PlayerGameStats.game_id == Game.id)
                .filter(
                    PlayerGameStats.player_id == teammate.id,
                    PlayerGameStats.minutes >= 15,
                    PlayerGameStats.usage_rate.isnot(None),
                )
                .order_by(desc(Game.date))
                .limit(10)
                .all()
            )
            if tm_games:
                tm_usage = sum(g.usage_rate for g in tm_games) / len(tm_games)
                tm_minutes = sum(g.minutes for g in tm_games) / len(tm_games)
                team_context_map[teammate.id] = {
                    "usage": tm_usage,
                    "minutes": tm_minutes,
                }
        _set_cached_usage(_team_usage_cache, team_usage_cache_key, team_context_map)

    missing_weighted_usage = 0.0
    healthy_teammates = []

    for teammate in teammates:
        # Check injury status
        status = _find_status_for_player_and_team(
            player_name=teammate.name,
            team_name=team.name,
            team_abbreviation=team.abbreviation,
            injuries=team_injuries or injuries,
        )
        tm_context = team_context_map.get(teammate.id)
        if isinstance(tm_context, dict):
            tm_usage = tm_context.get("usage")
            tm_minutes = tm_context.get("minutes")
        elif isinstance(tm_context, (int, float)):
            # Backward compatibility for prior cache format.
            tm_usage = float(tm_context)
            tm_minutes = 24.0
        else:
            tm_usage = None
            tm_minutes = None

        if tm_usage is None:
            continue

        minute_weight = max(0.35, min(1.35, (tm_minutes or 24.0) / 30.0))
        tm_weighted_usage = tm_usage * minute_weight

        inferred_out = teammate.id in inferred_out_ids

        # Minutes-led inclusion: absences from steady rotation players should count
        # even when usage isn't star-level.
        is_core_rotation = (tm_minutes or 0) >= 18.0

        if _status_indicates_unavailable(status) and is_core_rotation:
            missing_weighted_usage += tm_weighted_usage
            logger.info(
                f"✓ {teammate.name} OUT ({tm_usage:.1f}% usage, {tm_minutes or 0:.1f} mpg) - "
                f"redistributing {tm_weighted_usage:.1f} weighted usage"
            )
        elif inferred_out and is_core_rotation:
            # Fallback signal is weaker than official injury status.
            inferred_missing = tm_weighted_usage * 0.6
            missing_weighted_usage += inferred_missing
            logger.info(
                f"~ {teammate.name} inferred absent ({tm_usage:.1f}% usage, {tm_minutes or 0:.1f} mpg, "
                f"counting {inferred_missing:.1f} weighted usage)"
            )
        else:
            healthy_teammates.append((teammate.id, tm_weighted_usage))

    if missing_weighted_usage == 0 or not healthy_teammates:
        return 1.0

    total_healthy_weighted_usage = sum(weighted_usg for _, weighted_usg in healthy_teammates)

    if total_healthy_weighted_usage == 0:
        return 1.0

    player_weighted_usage = player_usage * player_minutes_weight
    redistribution_share = (
        (player_weighted_usage / total_healthy_weighted_usage) * missing_weighted_usage
    )

    # 5% usage increase ≈ 8-10% stat increase
    usage_boost_factor = 1.0 + (redistribution_share / player_usage) * 0.85

    # Cap at +15%
    usage_boost_factor = min(1.15, usage_boost_factor)

    if usage_boost_factor > 1.02:
        logger.info(
            f"✓ {player.name} injury boost: {usage_boost_factor:.3f}x "
            f"({missing_weighted_usage:.1f} weighted missing usage)"
        )

    return usage_boost_factor


def _infer_recent_absent_teammates(
    db: Session,
    team_id: int,
    game_date: date,
) -> set[int]:
    """
    Infer likely absences from the team's most recent completed game.

    This acts as a fallback when the external injury feed fails validation.
    """
    from app.models.player import Player, PlayerGameStats, Game

    last_game = (
        db.query(Game)
        .filter(
            ((Game.home_team_id == team_id) | (Game.away_team_id == team_id)),
            Game.home_score.isnot(None),
            Game.date < game_date,
        )
        .order_by(desc(Game.date))
        .first()
    )

    if not last_game:
        return set()

    team_player_ids = {
        p.id
        for p in db.query(Player.id).filter(
            Player.team_id == team_id,
            Player.is_active.is_(True),
        ).all()
    }
    if not team_player_ids:
        return set()

    played_ids = {
        s.player_id
        for s in db.query(PlayerGameStats.player_id)
        .filter(
            PlayerGameStats.game_id == last_game.id,
            PlayerGameStats.player_id.in_(team_player_ids),
            PlayerGameStats.minutes >= 1,
        )
        .all()
    }

    return team_player_ids - played_ids
