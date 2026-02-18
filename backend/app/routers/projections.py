# backend/app/routers/projections.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app.models.player import Player, Team, Game, PlayerGameStats, OddsLine
from app.services.projection_engine import (
    project_player,
    STAT_CONFIG,
)
from app.services.monte_carlo import (
    simulate_stat_distribution,
    calculate_hit_probability,
    calculate_expected_value,
    generate_confidence_intervals,
)
from app.services.projection_grader import calculate_model_accuracy

router = APIRouter(prefix="/projections", tags=["projections"])


def _next_game_date_with_odds(db: Session) -> date | None:
    """
    Returns the nearest date (today or upcoming) that has FanDuel odds lines.
    Checks today and tomorrow first, then up to 7 days ahead.
    This ensures projections always align with the same slate that has live lines.
    Falls back to next date with any scheduled games if no odds found.
    """
    # First: look for dates with FanDuel lines (today or tomorrow preferred)
    for days_ahead in range(8):
        check_date = date.today() + timedelta(days=days_ahead)
        games = db.query(Game).filter(Game.date == check_date).all()
        game_ids = [g.id for g in games]
        if game_ids:
            count = db.query(OddsLine).filter(
                OddsLine.game_id.in_(game_ids),
                OddsLine.sportsbook == 'fanduel',
            ).count()
            if count > 0:
                return check_date

    # Fallback: next date with any scheduled games
    for days_ahead in range(8):
        check_date = date.today() + timedelta(days=days_ahead)
        if db.query(Game).filter(Game.date == check_date).count() > 0:
            return check_date

    return date.today()


def _proj_to_dict(proj) -> dict:
    matchup_dict = None
    if proj.matchup:
        m = proj.matchup
        matchup_dict = {
            "opp_name":       m.opp_name,
            "opp_abbr":       m.opp_abbr,
            "opp_pace":       m.opp_pace,
            "def_rank":       m.def_rank,
            "matchup_grade":  m.matchup_grade,
            "pace_factor":    round(m.pace_factor, 3),
            "matchup_factor": round(m.matchup_factor, 3),
            "allowed_avg":    round(m.allowed_avg, 2) if m.allowed_avg else None,
            # Full defensive breakdown for this player's position group
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
        "player_id":      proj.player_id,
        "player_name":    proj.player_name,
        "team_name":      proj.team_name,
        "position":       proj.position,
        "stat_type":      proj.stat_type,
        "projected":      proj.projected,
        "season_avg":     proj.season_avg,
        "l5_avg":         proj.l5_avg,
        "l10_avg":        proj.l10_avg,
        "std_dev":        proj.std_dev,
        "floor":          proj.floor,
        "ceiling":        proj.ceiling,
        "games_played":   proj.games_played,
        "matchup":        matchup_dict,
        "line":           proj.line,
        "edge_pct":       proj.edge_pct,
        "over_prob":      proj.over_prob,
        "under_prob":     proj.under_prob,
        "recommendation": proj.recommendation,
        # Situational adjustments applied
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


# ── GET /projections/today ────────────────────────────────────────────────────
@router.get("/today")
def today_projections(
    stat_type: str = Query("points", description="Stat to project"),
    min_projected: float = Query(0.0, description="Minimum projected value filter"),
    position:  Optional[str] = Query(None, description="Filter by position: G, G-F, F, F-C, C"),
    db: Session = Depends(get_db),
):
    """
    All player projections for today's games, sorted by projected value.
    Use this as the main dashboard feed.
    """
    if stat_type not in STAT_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stat_type. Options: {list(STAT_CONFIG.keys())}"
        )

    game_date = _next_game_date_with_odds(db)
    if not game_date:
        return {"projections": [], "date": str(date.today())}

    games = db.query(Game).filter(Game.date == game_date).all()

    results = []
    for game in games:
        for team_id, opp_id in [
            (game.home_team_id, game.away_team_id),
            (game.away_team_id, game.home_team_id),
        ]:
            if position:
                players = db.query(Player).filter(
                    Player.team_id == team_id,
                    Player.is_active == True,
                    Player.position == position.upper(),
                ).all()
            else:
                players = db.query(Player).filter(
                    Player.team_id == team_id,
                    Player.is_active == True,
                ).all()

            for player in players:
                proj = project_player(db, player.id, stat_type, opp_id)
                if proj and proj.projected >= min_projected:
                    results.append(_proj_to_dict(proj))

    results.sort(key=lambda x: x["projected"], reverse=True)
    return {
        "date":        str(game_date),
        "stat_type":   stat_type,
        "count":       len(results),
        "projections": results,
    }


# ── GET /projections/edge-finder ──────────────────────────────────────────────
@router.get("/edge-finder")
def edge_finder(
    db: Session = Depends(get_db),
):
    """
    Placeholder for the edge finder.
    Will be powered once odds lines are stored in the database.
    Returns top projections for today sorted by matchup grade
    as a proxy for edge until lines are integrated.
    """
    game_date = _next_game_date_with_odds(db)
    if not game_date:
        return {"edges": [], "message": "No games found"}

    games = db.query(Game).filter(Game.date == game_date).all()

    results = []
    for game in games:
        for team_id, opp_id in [
            (game.home_team_id, game.away_team_id),
            (game.away_team_id, game.home_team_id),
        ]:
            players = db.query(Player).filter(
                Player.team_id == team_id,
                Player.is_active == True,
            ).all()

            for player in players:
                proj = project_player(db, player.id, "points", opp_id)
                if not proj or proj.projected <= 0:
                    continue

                # Score the matchup quality (lower def_rank = easier matchup)
                rank = proj.matchup.def_rank if proj.matchup else 15
                matchup_score = (30 - rank) if rank else 0

                results.append({
                    **_proj_to_dict(proj),
                    "matchup_score": matchup_score,
                })

    # Sort by matchup score (best matchup first) then projected
    results.sort(key=lambda x: (x["matchup_score"], x["projected"]), reverse=True)
    return {
        "date":    str(game_date),
        "note":    "Edge % will populate once odds lines are integrated. Sorted by matchup favorability.",
        "count":   len(results),
        "edges":   results[:50],
    }


# ── POST /projections/with-line ───────────────────────────────────────────────
@router.post("/with-line")
def project_with_line(
    player_id:   int,
    stat_type:   str,
    line:        float,
    opp_team_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Project a player against a specific sportsbook line.
    Returns edge %, over/under probability, and recommendation.
    This is the core endpoint for prop betting analysis.
    """
    if stat_type not in STAT_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid stat_type")

    proj = project_player(db, player_id, stat_type, opp_team_id, line)
    if not proj:
        raise HTTPException(status_code=404, detail="Player not found or no stats available")

    return _proj_to_dict(proj)


# ── GET /projections/team/{team_id} ───────────────────────────────────────────
@router.get("/team/{team_id}")
def team_projections(
    team_id:    int,
    stat_type:  str = Query("points"),
    opp_team_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """All player projections for a specific team."""
    if stat_type not in STAT_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid stat_type")

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    players = db.query(Player).filter(
        Player.team_id == team_id,
        Player.is_active == True,
    ).all()

    results = []
    for player in players:
        proj = project_player(db, player.id, stat_type, opp_team_id)
        if proj and proj.projected > 0:
            results.append(_proj_to_dict(proj))

    results.sort(key=lambda x: x["projected"], reverse=True)
    return {
        "team_id":     team_id,
        "team_name":   team.name,
        "stat_type":   stat_type,
        "count":       len(results),
        "projections": results,
    }


# ── GET /projections/matchup-rankings ─────────────────────────────────────────
@router.get("/matchup-rankings")
def matchup_rankings(
    stat_type: str = Query("points"),
    position:  str = Query("G", description="Position bucket: G, GF, F, FC, C"),
    db: Session = Depends(get_db),
):
    """
    Rank all 30 teams by how many points/rebounds/etc they allow
    to a specific position group. Great for finding soft matchups.
    """
    # Map position param → column suffix
    pos_map = {"G": "g", "GF": "gf", "F": "f", "FC": "fc", "C": "c"}
    col_suffix = pos_map.get(position.upper())
    if not col_suffix:
        raise HTTPException(status_code=400, detail="Invalid position. Use: G, GF, F, FC, C")

    stat_map = {
        "points": "pts", "rebounds": "reb", "assists": "ast",
        "steals": "stl", "blocks": "blk",
    }
    stat_prefix = stat_map.get(stat_type)
    if not stat_prefix:
        raise HTTPException(status_code=400, detail="Use: points, rebounds, assists, steals, blocks")

    avg_col  = f"{stat_prefix}_allowed_{col_suffix}"
    rank_col = f"{stat_prefix}_rank_{col_suffix}"

    teams = db.query(Team).filter(
        getattr(Team, avg_col) != None
    ).all()

    result = []
    for t in teams:
        result.append({
            "team_id":     t.id,
            "team_name":   t.name,
            "abbr":        t.abbreviation,
            "record":      f"{t.wins}-{t.losses}",
            "allowed_avg": round(_safe(getattr(t, avg_col)), 2),
            "rank":        getattr(t, rank_col),
            "matchup_grade": _grade_from_rank(getattr(t, rank_col)),
        })

    result.sort(key=lambda x: x["rank"] or 99)
    return {
        "stat_type": stat_type,
        "position":  position.upper(),
        "note":      "Rank 1 = most permissive (best matchup). Rank 30 = toughest.",
        "teams":     result,
    }


# ── POST /projections/simulate ────────────────────────────────────────────────
@router.post("/simulate")
def simulate_prop(
    player_id:   int,
    stat_type:   str,
    line:        float,
    opp_team_id: Optional[int] = None,
    over_odds:   int = -110,
    under_odds:  int = -110,
    db: Session = Depends(get_db),
):
    """
    Run 10,000 Monte Carlo simulations for a prop bet.
    
    Returns:
        Full distribution analysis with percentiles, hit probability,
        expected value, and Kelly Criterion bet sizing.
    """
    if stat_type not in STAT_CONFIG:
        raise HTTPException(400, "Invalid stat_type")
    
    proj = project_player(db, player_id, stat_type, opp_team_id, line)
    if not proj:
        raise HTTPException(404, "No projection available")
    
    sim_result = simulate_stat_distribution(
        mean=proj.projected,
        std_dev=proj.std_dev,
        n_simulations=10000,
    )
    
    over_prob, under_prob = calculate_hit_probability(
        mean=proj.projected,
        std_dev=proj.std_dev,
        line=line,
        n_simulations=10000,
    )
    
    ev = calculate_expected_value(
        over_prob=over_prob,
        over_odds=over_odds,
        under_prob=under_prob,
        under_odds=under_odds,
    )
    
    confidence = generate_confidence_intervals(proj.projected, proj.std_dev)
    
    return {
        "player_id": player_id,
        "player_name": proj.player_name,
        "team_name": proj.team_name,
        "stat_type": stat_type,
        "line": line,
        "projected": proj.projected,
        "std_dev": proj.std_dev,
        "monte_carlo": {
            **sim_result,
            "over_probability": over_prob,
            "under_probability": under_prob,
            "expected_value": ev,
            "confidence_intervals": confidence,
        },
        "adjustments": {
            "home_factor": proj.home_factor,
            "rest_factor": proj.rest_factor,
            "blowout_factor": proj.blowout_factor,
            "injury_factor": proj.injury_factor,
            "form_factor": proj.form_factor,
            "opp_strength": proj.opp_strength,
        }
    }


# ── GET /projections/accuracy ─────────────────────────────────────────────────
@router.get("/accuracy")
def model_accuracy(
    stat_type:  str = Query("points"),
    days_back:  int = Query(30, le=365),
    min_edge:   Optional[float] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Historical model accuracy metrics.
    
    Shows:
    - Overall win rate
    - Win rate by edge size
    - Mean Absolute Error
    - Hypothetical profit/loss
    """
    return calculate_model_accuracy(
        db=db,
        stat_type=stat_type,
        days_back=days_back,
        min_edge=min_edge,
    )


def _safe(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _grade_from_rank(rank):
    if rank is None:
        return "Unknown"
    if rank <= 5:   return "Elite"
    if rank <= 10:  return "Good"
    if rank <= 20:  return "Neutral"
    if rank <= 25:  return "Tough"
    return "Lockdown"