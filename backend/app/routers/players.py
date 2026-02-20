# backend/app/routers/players.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional

from app.database import get_db
from app.models.player import Player, PlayerGameStats, Team, Game
from app.services.projection_engine import (
    project_player,
    get_player_stat_lines,
    compute_stat_averages,
    STAT_CONFIG,
)

router = APIRouter(prefix="/players", tags=["players"])


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _projection_to_dict(proj) -> dict:
    if proj is None:
        return {}

    matchup_dict = None
    if proj.matchup:
        m = proj.matchup
        matchup_dict = {
            "opp_team_id":    m.opp_team_id,
            "opp_name":       m.opp_name,
            "opp_abbr":       m.opp_abbr,
            "opp_pace":       m.opp_pace,
            "allowed_avg":    round(m.allowed_avg, 2) if m.allowed_avg else None,
            "def_rank":       m.def_rank,
            "pace_factor":    round(m.pace_factor, 3),
            "matchup_factor": round(m.matchup_factor, 3),
            "matchup_grade":  m.matchup_grade,
            "defense": {
                "pts_allowed": round(m.pts_allowed, 2) if m.pts_allowed else None,
                "reb_allowed": round(m.reb_allowed, 2) if m.reb_allowed else None,
                "ast_allowed": round(m.ast_allowed, 2) if m.ast_allowed else None,
                "stl_allowed": round(m.stl_allowed, 2) if m.stl_allowed else None,
                "blk_allowed": round(m.blk_allowed, 2) if m.blk_allowed else None,
                "pts_rank":    m.pts_rank,
                "reb_rank":    m.reb_rank,
                "ast_rank":    m.ast_rank,
                "stl_rank":    m.stl_rank,
                "blk_rank":    m.blk_rank,
            },
        }

    return {
        "projected":       proj.projected,
        "season_avg":      proj.season_avg,
        "l5_avg":          proj.l5_avg,
        "l10_avg":         proj.l10_avg,
        "std_dev":         proj.std_dev,
        "floor":           proj.floor,
        "ceiling":         proj.ceiling,
        "games_played":    proj.games_played,
        "matchup":         matchup_dict,
        "line":            proj.line,
        "edge_pct":        proj.edge_pct,
        "over_prob":       proj.over_prob,
        "under_prob":      proj.under_prob,
        "recommendation":  proj.recommendation,
        "adjustments": {
            "home_factor":     proj.home_factor,
            "rest_factor":     proj.rest_factor,
            "blowout_factor":  proj.blowout_factor,
            "injury_factor":   proj.injury_factor,
            "form_factor":     proj.form_factor,
            "opp_strength":    proj.opp_strength,
            "is_back_to_back": proj.is_back_to_back,
        },
    }


# ── GET /players ──────────────────────────────────────────────────────────────
@router.get("")
def list_players(
    team_id:  Optional[int] = Query(None),
    position: Optional[str] = Query(None),
    search:   Optional[str] = Query(None),
    limit:    int           = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """List players with optional filters."""
    q = db.query(Player, Team).join(Team, Player.team_id == Team.id, isouter=True)

    if team_id:
        q = q.filter(Player.team_id == team_id)
    if position:
        q = q.filter(Player.position == position.upper())
    if search:
        q = q.filter(Player.name.ilike(f"%{search}%"))

    q = q.filter(Player.is_active == True).limit(limit)
    rows = q.all()

    return {
        "players": [
            {
                "id":           p.id,
                "name":         p.name,
                "position":     p.position,
                "jersey":       p.jersey_number,
                "team_id":      p.team_id,
                "team_name":    t.name if t else None,
                "team_abbr":    t.abbreviation if t else None,
            }
            for p, t in rows
        ],
        "count": len(rows),
    }


# ── GET /players/{player_id}/profile ─────────────────────────────────────────
@router.get("/{player_id}/profile")
def player_profile(
    player_id: int,
    db: Session = Depends(get_db),
):
    """
    Full player profile: bio, team info, season/L5/L10 averages for
    all stat types, and last 10 game log.
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    team = db.query(Team).filter(Team.id == player.team_id).first()

    # ── Compute averages for every stat type ──────────────────────────────────
    averages = {}
    for stat_type, (stat_col, _) in STAT_CONFIG.items():
        values = get_player_stat_lines(db, player_id, stat_col)
        avgs   = compute_stat_averages(values)
        averages[stat_type] = {
            "season_avg":   round(avgs.season_avg, 2),
            "l5_avg":       round(avgs.l5_avg, 2),
            "l10_avg":      round(avgs.l10_avg, 2),
            "games_played": avgs.games_played,
        }

    # ── Last 10 game log ──────────────────────────────────────────────────────
    recent_rows = (
        db.query(PlayerGameStats, Game)
        .join(Game, PlayerGameStats.game_id == Game.id)
        .filter(PlayerGameStats.player_id == player_id)
        .order_by(desc(Game.date))
        .limit(10)
        .all()
    )

    game_log = []
    for stat, game in recent_rows:
        home = db.query(Team).filter(Team.id == game.home_team_id).first()
        away = db.query(Team).filter(Team.id == game.away_team_id).first()
        is_home = game.home_team_id == player.team_id
        opp = away if is_home else home

        game_log.append({
            "date":        str(game.date),
            "opponent":    opp.abbreviation if opp else "?",
            "home_away":   "vs" if is_home else "@",
            "result":      _game_result(game, player.team_id),
            "minutes":     round(_safe(stat.minutes), 1),
            "points":      stat.points,
            "rebounds":    stat.rebounds,
            "assists":     stat.assists,
            "steals":      stat.steals,
            "blocks":      stat.blocks,
            "turnovers":   stat.turnovers,
            "pra":         stat.pra,
            "fg":          f"{stat.fgm}/{stat.fga}",
            "fg_pct":      round(_safe(stat.fg_pct) * 100, 1),
            "fg3":         f"{stat.fg3m}/{stat.fg3a}",
            "ft":          f"{stat.ftm}/{stat.fta}",
            "usage_rate":  round(_safe(stat.usage_rate) * 100, 1),
            "plus_minus":  stat.plus_minus,
            "fantasy_pts": round(_safe(stat.fantasy_points), 1),
        })

    return {
        "player": {
            "id":           player.id,
            "name":         player.name,
            "position":     player.position,
            "jersey":       player.jersey_number,
            "team_id":      player.team_id,
            "team_name":    team.name if team else None,
            "team_abbr":    team.abbreviation if team else None,
        },
        "averages": averages,
        "game_log": game_log,
    }


# ── GET /players/{player_id}/projection ──────────────────────────────────────
@router.get("/{player_id}/projection")
def player_projection(
    player_id:   int,
    stat_type:   str           = Query("points"),
    opp_team_id: Optional[int] = Query(None),
    line:        Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Project a player for a specific stat type.
    Optionally provide opp_team_id for matchup adjustments
    and line for edge/probability calculation.
    """
    if stat_type not in STAT_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stat_type. Choose from: {list(STAT_CONFIG.keys())}"
        )

    proj = project_player(db, player_id, stat_type, opp_team_id, line)
    if not proj:
        raise HTTPException(status_code=404, detail="Player not found or no stats available")

    return {
        "player_id":    proj.player_id,
        "player_name":  proj.player_name,
        "team_name":    proj.team_name,
        "position":     proj.position,
        "stat_type":    proj.stat_type,
        **_projection_to_dict(proj),
    }


# ── GET /players/{player_id}/all-projections ─────────────────────────────────
@router.get("/{player_id}/all-projections")
def player_all_projections(
    player_id:   int,
    opp_team_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Project a player across ALL stat types at once.
    Useful for building a full player card.
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    projections = {}
    for stat_type in STAT_CONFIG:
        proj = project_player(db, player_id, stat_type, opp_team_id)
        if proj:
            projections[stat_type] = _projection_to_dict(proj)

    team = db.query(Team).filter(Team.id == player.team_id).first()

    return {
        "player": {
            "id":        player.id,
            "name":      player.name,
            "position":  player.position,
            "team_name": team.name if team else None,
            "team_abbr": team.abbreviation if team else None,
        },
        "projections": projections,
    }

# ──────────────────────────────────────────────────────────────────────────────
# ADD THIS TO YOUR backend/app/routers/players.py
# Place it AFTER the player_all_projections function
# ──────────────────────────────────────────────────────────────────────────────

# backend/app/routers/players.py
# Update the /players/{player_id}/game-log endpoint to include all stats

@router.get("/{player_id}/game-log")
def get_player_game_log(
    
    player_id: int,
    last: int = Query(20, description="Number of recent games to return"),
    db: Session = Depends(get_db),
):
    """
    Get recent game log for a player with all stats including combos.
    Returns games in reverse chronological order (most recent first).
    """
    from app.models.player import PlayerGameStats, Game
    from sqlalchemy import desc
    
    # Fetch recent games
    game_stats = (
        db.query(PlayerGameStats, Game)
        .join(Game, PlayerGameStats.game_id == Game.id)
        .filter(PlayerGameStats.player_id == player_id)
        .order_by(desc(Game.date))
        .limit(last)
        .all()
    )
    
    if not game_stats:
        return []
    
    # Get player's team to determine opponents
    from app.models.player import Player
    player = db.query(Player).filter(Player.id == player_id).first()
    
    result = []
    for stat, game in game_stats:
        # Determine opponent
        if player and player.team_id == game.home_team_id:
            opp_team_id = game.away_team_id
            is_home = True
        else:
            opp_team_id = game.home_team_id
            is_home = False
        
        # Get opponent abbreviation
        from app.models.player import Team
        opp_team = db.query(Team).filter(Team.id == opp_team_id).first()
        opp_abbr = opp_team.abbreviation if opp_team else "???"
        
        # Determine result
        if game.status == "final":
            if is_home:
                won = game.home_score > game.away_score
            else:
                won = game.away_score > game.home_score
            result_str = "W" if won else "L"
        else:
            result_str = "SCH"
        
        # Build response with ALL stats
        result.append({
            "game_id": game.id,
            "date": str(game.date),
            "opponent": opp_team.name if opp_team else "Unknown",
            "opp_abbr": opp_abbr,
            "is_home": is_home,
            "result": result_str,
            
            # Basic stats
            "minutes": stat.minutes,
            "points": stat.points,
            "rebounds": stat.rebounds,
            "assists": stat.assists,
            "steals": stat.steals,
            "blocks": stat.blocks,
            
            # Shooting stats
            "fgm": stat.fgm,
            "fga": stat.fga,
            "fg_pct": stat.fg_pct,
            "fg3m": stat.fg3m,  # ← 3-POINTERS MADE
            "fg3a": stat.fg3a,
            "fg3_pct": stat.fg3_pct,
            "ftm": stat.ftm,
            "fta": stat.fta,
            "ft_pct": stat.ft_pct,
            
            # Other stats
            "oreb": stat.oreb,
            "dreb": stat.dreb,
            "turnovers": stat.turnovers,
            "plus_minus": stat.plus_minus,
            
            # Combo stats (pre-calculated or calculate on the fly)
            "pra": stat.pra if hasattr(stat, 'pra') else (stat.points + stat.rebounds + stat.assists),
            "pr": stat.pr if hasattr(stat, 'pr') else (stat.points + stat.rebounds),
            "pa": stat.pa if hasattr(stat, 'pa') else (stat.points + stat.assists),
            "ra": stat.ra if hasattr(stat, 'ra') else (stat.rebounds + stat.assists),
            
            # Also include with alternative name for compatibility
            "three_pointers_made": stat.fg3m,
        })
    
    return result
# ── Helpers ───────────────────────────────────────────────────────────────────
def _game_result(game: Game, team_id: int) -> str:
    if game.home_score is None or game.away_score is None:
        return "—"
    is_home = game.home_team_id == team_id
    my_score  = game.home_score if is_home else game.away_score
    opp_score = game.away_score if is_home else game.home_score
    result = "W" if my_score > opp_score else "L"
    return f"{result} {my_score}-{opp_score}"