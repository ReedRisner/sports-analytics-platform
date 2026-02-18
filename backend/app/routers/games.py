# backend/app/routers/games.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app.models.player import Player, Team, Game, PlayerGameStats
from app.services.projection_engine import (
    project_player,
    get_matchup_context,
    STAT_CONFIG,
)

router = APIRouter(prefix="/games", tags=["games"])

FEATURED_STATS = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'pra']


def _next_game_date(db: Session) -> date | None:
    """
    Returns the next date (today or forward) that has games scheduled.
    Looks up to 7 days ahead. Falls back to most recent completed game
    if nothing upcoming is found (e.g. end of season).
    """
    today = date.today()
    for days_ahead in range(8):
        check_date = today + timedelta(days=days_ahead)
        count = db.query(Game).filter(Game.date == check_date).count()
        if count > 0:
            return check_date
    # Fallback: most recent completed game
    last = db.query(Game).filter(
        Game.home_score != None
    ).order_by(desc(Game.date)).first()
    return last.date if last else None


def _safe(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _team_dict(team: Team) -> dict:
    if not team:
        return {}
    return {
        "id":               team.id,
        "name":             team.name,
        "abbreviation":     team.abbreviation,
        "record":           f"{team.wins}-{team.losses}",
        "pace":             team.pace,
        "offensive_rating": team.offensive_rating,
        "defensive_rating": team.defensive_rating,
        "points_per_game":  team.points_per_game,
        "opp_points_per_game": team.opp_points_per_game,
    }


def _proj_summary(proj) -> dict:
    if not proj:
        return {}
    return {
        "projected":      proj.projected,
        "l5_avg":         proj.l5_avg,
        "l10_avg":        proj.l10_avg,
        "season_avg":     proj.season_avg,
        "floor":          proj.floor,
        "ceiling":        proj.ceiling,
        "std_dev":        proj.std_dev,
        "matchup_grade":  proj.matchup.matchup_grade if proj.matchup else None,
        "matchup_factor": round(proj.matchup.matchup_factor, 3) if proj.matchup else None,
        "def_rank":       proj.matchup.def_rank if proj.matchup else None,
    }


# ── GET /games ────────────────────────────────────────────────────────────────
@router.get("")
def list_games(
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """List most recent games with scores."""
    games = (
        db.query(Game)
        .filter(Game.home_score != None)
        .order_by(desc(Game.date))
        .limit(limit)
        .all()
    )

    result = []
    for g in games:
        home = db.query(Team).filter(Team.id == g.home_team_id).first()
        away = db.query(Team).filter(Team.id == g.away_team_id).first()
        result.append({
            "id":          g.id,
            "nba_game_id": g.nba_game_id,
            "date":        str(g.date),
            "status":      g.status,
            "home_team":   _team_dict(home),
            "away_team":   _team_dict(away),
            "home_score":  g.home_score,
            "away_score":  g.away_score,
        })
    return {"games": result, "count": len(result)}


# ── GET /games/today ──────────────────────────────────────────────────────────
@router.get("/today")
def today_games(
    stat_types: str = Query("points,rebounds,assists,pra", description="Comma-separated stat types"),
    db: Session = Depends(get_db),
):
    """
    Returns today's games (or most recent game day if no games today).
    For each game, returns both teams' rosters with projections and matchup context.
    """
    requested_stats = [s.strip() for s in stat_types.split(",") if s.strip() in STAT_CONFIG]
    if not requested_stats:
        requested_stats = ['points', 'rebounds', 'assists', 'pra']

    # Find the next upcoming game date (today or forward, up to 7 days)
    game_date = _next_game_date(db)
    if not game_date:
        return {"games": [], "date": str(date.today())}

    # Get all games on that date
    games = db.query(Game).filter(Game.date == game_date).all()

    result = []
    for g in games:
        home = db.query(Team).filter(Team.id == g.home_team_id).first()
        away = db.query(Team).filter(Team.id == g.away_team_id).first()

        game_data = {
            "id":         g.id,
            "date":       str(g.date),
            "status":     g.status,
            "home_score": g.home_score,
            "away_score": g.away_score,
            "home_team":  _team_dict(home),
            "away_team":  _team_dict(away),
            "home_players": _build_player_projections(db, g.home_team_id, g.away_team_id, requested_stats),
            "away_players": _build_player_projections(db, g.away_team_id, g.home_team_id, requested_stats),
        }
        result.append(game_data)

    return {
        "date":  str(game_date),
        "games": result,
        "count": len(result),
    }


# ── GET /games/{game_id} ──────────────────────────────────────────────────────
@router.get("/{game_id}")
def get_game(
    game_id:    int,
    stat_types: str = Query("points,rebounds,assists,pra"),
    db: Session = Depends(get_db),
):
    """
    Full game detail: both teams, all player projections, matchup grades.
    """
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    requested_stats = [s.strip() for s in stat_types.split(",") if s.strip() in STAT_CONFIG]
    if not requested_stats:
        requested_stats = ['points', 'rebounds', 'assists', 'pra']

    home = db.query(Team).filter(Team.id == game.home_team_id).first()
    away = db.query(Team).filter(Team.id == game.away_team_id).first()

    return {
        "id":           game.id,
        "nba_game_id":  game.nba_game_id,
        "date":         str(game.date),
        "status":       game.status,
        "home_score":   game.home_score,
        "away_score":   game.away_score,
        "home_team":    _team_dict(home),
        "away_team":    _team_dict(away),
        "home_players": _build_player_projections(db, game.home_team_id, game.away_team_id, requested_stats),
        "away_players": _build_player_projections(db, game.away_team_id, game.home_team_id, requested_stats),
    }


# ── GET /games/{game_id}/top-props ────────────────────────────────────────────
@router.get("/{game_id}/top-props")
def game_top_props(
    game_id:    int,
    stat_type:  str = Query("points"),
    top_n:      int = Query(10, le=30),
    db: Session = Depends(get_db),
):
    """
    Return the top N projected players in a game for a given stat.
    Useful for quick matchup breakdowns.
    """
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if stat_type not in STAT_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid stat_type")

    results = []
    for team_id, opp_id in [
        (game.home_team_id, game.away_team_id),
        (game.away_team_id, game.home_team_id),
    ]:
        players = db.query(Player).filter(
            Player.team_id == team_id,
            Player.is_active == True,
        ).all()

        team = db.query(Team).filter(Team.id == team_id).first()

        for player in players:
            proj = project_player(db, player.id, stat_type, opp_id)
            if proj and proj.projected > 0:
                results.append({
                    "player_id":     player.id,
                    "player_name":   player.name,
                    "team_abbr":     team.abbreviation if team else "",
                    "position":      player.position,
                    "stat_type":     stat_type,
                    "projected":     proj.projected,
                    "l5_avg":        proj.l5_avg,
                    "season_avg":    proj.season_avg,
                    "floor":         proj.floor,
                    "ceiling":       proj.ceiling,
                    "matchup_grade": proj.matchup.matchup_grade if proj.matchup else None,
                    "def_rank":      proj.matchup.def_rank if proj.matchup else None,
                })

    results.sort(key=lambda x: x["projected"], reverse=True)
    return {"game_id": game_id, "stat_type": stat_type, "players": results[:top_n]}


# ── Internal helper ───────────────────────────────────────────────────────────
def _build_player_projections(
    db: Session,
    team_id: int,
    opp_team_id: int,
    stat_types: list[str],
) -> list[dict]:
    """
    For all active players on a team, compute projections vs the opponent.
    Returns list sorted by projected points desc.
    """
    players = db.query(Player).filter(
        Player.team_id == team_id,
        Player.is_active == True,
    ).all()

    result = []
    for player in players:
        player_data = {
            "player_id":   player.id,
            "player_name": player.name,
            "position":    player.position,
            "jersey":      player.jersey_number,
            "projections": {},
        }

        has_data = False
        for stat in stat_types:
            proj = project_player(db, player.id, stat, opp_team_id)
            if proj and proj.projected > 0:
                player_data["projections"][stat] = _proj_summary(proj)
                has_data = True

        if has_data:
            result.append(player_data)

    # Sort by projected points if available, else projected pra
    def sort_key(p):
        pts  = p["projections"].get("points", {}).get("projected", 0)
        pra  = p["projections"].get("pra", {}).get("projected", 0)
        return pts if pts else pra

    result.sort(key=sort_key, reverse=True)
    return result