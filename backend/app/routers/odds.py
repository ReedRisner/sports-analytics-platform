# backend/app/routers/odds.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app.models.player import Player, Team, Game, OddsLine
from app.services.projection_engine import project_player, STAT_CONFIG

router = APIRouter(prefix="/odds", tags=["odds"])


def _safe(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _nearest_game_date(db) -> date | None:
    """
    Returns the nearest date (today or up to 3 days ahead) that has
    odds lines stored. Falls back to today if nothing found.
    """
    for days_ahead in range(4):
        check_date = date.today() + timedelta(days=days_ahead)
        games = db.query(Game).filter(Game.date == check_date).all()
        game_ids = [g.id for g in games]
        if game_ids:
            from app.models.player import OddsLine as OL
            count = db.query(OL).filter(OL.game_id.in_(game_ids)).count()
            if count > 0:
                return check_date
    # fallback — return today even if no lines, so endpoints don't break
    return date.today()


# ── GET /odds/today ───────────────────────────────────────────────────────────
@router.get("/today")
def todays_odds(
    stat_type:  Optional[str] = Query(None, description="Filter by stat: points, rebounds, assists"),
    sportsbook: Optional[str] = Query(None, description="Filter by book: fanduel, draftkings, etc."),
    db: Session = Depends(get_db),
):
    """
    All prop lines fetched for today's games.
    Shows raw lines without projections.
    """
    today = _nearest_game_date(db)
    games = db.query(Game).filter(Game.date == today).all()
    game_ids = [g.id for g in games]

    if not game_ids:
        return {"lines": [], "date": str(today), "message": "No games or lines found in next 3 days"}

    q = db.query(OddsLine).filter(OddsLine.game_id.in_(game_ids))
    if stat_type:
        q = q.filter(OddsLine.stat_type == stat_type)
    if sportsbook:
        q = q.filter(OddsLine.sportsbook == sportsbook)

    lines = q.all()

    result = []
    for ol in lines:
        player = db.query(Player).filter(Player.id == ol.player_id).first()
        team   = db.query(Team).filter(Team.id == player.team_id).first() if player else None
        result.append({
            "player_id":   ol.player_id,
            "player_name": player.name if player else "Unknown",
            "team_abbr":   team.abbreviation if team else "?",
            "stat_type":   ol.stat_type,
            "sportsbook":  ol.sportsbook,
            "line":        ol.line,
            "over_odds":   ol.over_odds,
            "under_odds":  ol.under_odds,
            "fetched_at":  ol.fetched_at.isoformat() if ol.fetched_at else None,
        })

    return {
        "date":  str(today),
        "count": len(result),
        "lines": result,
    }


# ── GET /odds/edge-finder ─────────────────────────────────────────────────────
@router.get("/edge-finder")
def edge_finder(
    stat_type:    str   = Query("points"),
    sportsbook:   str   = Query("fanduel"),
    min_edge_pct: float = Query(3.0, description="Minimum edge % to show"),
    db: Session = Depends(get_db),
):
    """
    THE core endpoint. Compares our projections against real sportsbook lines.
    Returns players where our model disagrees with the book by min_edge_pct or more.
    """
    today = _nearest_game_date(db)
    games = db.query(Game).filter(Game.date == today).all()
    game_ids = [g.id for g in games]

    if not game_ids:
        return {"edges": [], "message": "No games or lines found in next 3 days"}

    # Get all lines for today matching filters
    lines = db.query(OddsLine).filter(
        OddsLine.game_id.in_(game_ids),
        OddsLine.stat_type  == stat_type,
        OddsLine.sportsbook == sportsbook,
    ).all()

    if not lines:
        return {
            "edges":   [],
            "message": f"No {sportsbook} lines found for {stat_type} today. "
                       f"Try running the odds fetcher or check another sportsbook.",
        }

    results = []
    for ol in lines:
        # Find the game this player is in to get their opponent
        game   = db.query(Game).filter(Game.id == ol.game_id).first()
        player = db.query(Player).filter(Player.id == ol.player_id).first()
        if not game or not player:
            continue

        # Determine opponent team
        opp_team_id = (
            game.away_team_id
            if game.home_team_id == player.team_id
            else game.home_team_id
        )

        # Run projection WITH the sportsbook line
        proj = project_player(
            db          = db,
            player_id   = ol.player_id,
            stat_type   = stat_type,
            opp_team_id = opp_team_id,
            line        = ol.line,
        )
        if not proj or proj.projected <= 0:
            continue

        # Only include if edge is meaningful
        if abs(proj.edge_pct or 0) < min_edge_pct:
            continue

        team = db.query(Team).filter(Team.id == player.team_id).first()
        opp  = db.query(Team).filter(Team.id == opp_team_id).first()

        results.append({
            "player_id":      player.id,
            "player_name":    player.name,
            "team_abbr":      team.abbreviation if team else "?",
            "opp_abbr":       opp.abbreviation if opp else "?",
            "position":       player.position,
            "stat_type":      stat_type,
            "sportsbook":     sportsbook,
            "line":           ol.line,
            "over_odds":      ol.over_odds,
            "under_odds":     ol.under_odds,
            "projected":      proj.projected,
            "season_avg":     proj.season_avg,
            "l5_avg":         proj.l5_avg,
            "l10_avg":        proj.l10_avg,
            "edge_pct":       proj.edge_pct,
            "over_prob":      proj.over_prob,
            "under_prob":     proj.under_prob,
            "recommendation": proj.recommendation,
            "floor":          proj.floor,
            "ceiling":        proj.ceiling,
            "std_dev":        proj.std_dev,
            "matchup_grade":  proj.matchup.matchup_grade if proj.matchup else None,
            "def_rank":       proj.matchup.def_rank if proj.matchup else None,
        })

    # Sort by absolute edge descending
    results.sort(key=lambda x: abs(x["edge_pct"] or 0), reverse=True)

    return {
        "date":       str(today),
        "stat_type":  stat_type,
        "sportsbook": sportsbook,
        "count":      len(results),
        "edges":      results,
    }


# ── GET /odds/player/{player_id} ─────────────────────────────────────────────
@router.get("/player/{player_id}")
def player_odds(
    player_id: int,
    db: Session = Depends(get_db),
):
    """
    All current lines for a specific player across all sportsbooks and stat types.
    Includes projection comparison for each line.
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    today = _nearest_game_date(db)
    games = db.query(Game).filter(Game.date == today).all()
    game_ids = [g.id for g in games]

    lines = db.query(OddsLine).filter(
        OddsLine.player_id == player_id,
        OddsLine.game_id.in_(game_ids),
    ).all()

    if not lines:
        return {
            "player_name": player.name,
            "lines":       [],
            "message":     "No lines found for this player today",
        }

    # Find opponent
    game = db.query(Game).filter(Game.id == lines[0].game_id).first()
    opp_team_id = None
    if game:
        opp_team_id = (
            game.away_team_id
            if game.home_team_id == player.team_id
            else game.home_team_id
        )

    result = []
    seen_stats = set()

    for ol in lines:
        proj = project_player(
            db          = db,
            player_id   = player_id,
            stat_type   = ol.stat_type,
            opp_team_id = opp_team_id,
            line        = ol.line,
        )

        result.append({
            "stat_type":      ol.stat_type,
            "sportsbook":     ol.sportsbook,
            "line":           ol.line,
            "over_odds":      ol.over_odds,
            "under_odds":     ol.under_odds,
            "projected":      proj.projected if proj else None,
            "edge_pct":       proj.edge_pct if proj else None,
            "over_prob":      proj.over_prob if proj else None,
            "recommendation": proj.recommendation if proj else None,
            "fetched_at":     ol.fetched_at.isoformat() if ol.fetched_at else None,
        })

    result.sort(key=lambda x: (x["stat_type"], x["sportsbook"]))
    return {
        "player_id":   player_id,
        "player_name": player.name,
        "date":        str(today),
        "lines":       result,
    }


# ── POST /odds/fetch ──────────────────────────────────────────────────────────
@router.post("/fetch")
def trigger_odds_fetch(db: Session = Depends(get_db)):
    """
    Manually trigger an odds fetch. Useful for testing without
    waiting for the scheduled job.
    """
    from app.services.odds_fetcher import fetch_todays_odds
    result = fetch_todays_odds(db=db)
    return result