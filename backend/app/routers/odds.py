# backend/app/routers/odds.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import date, timedelta

from app.database import get_db
from app.models.player import Player, Team, Game, OddsLine
from app.services.projection_engine import project_player, STAT_CONFIG
from app.services.projection_saver import save_projection
from app.services.streak_calculator import calculate_streak

router = APIRouter(prefix="/odds", tags=["odds"])


def _safe(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _calculate_ev(probability: float, odds: int) -> float:
    """
    Calculate Expected Value for a bet.
    
    Args:
        probability: Win probability as decimal (e.g., 0.65 for 65%)
        odds: American odds (e.g., -110, +150)
    
    Returns:
        EV as dollar amount per $100 bet
    """
    if probability <= 0 or probability >= 1:
        return 0.0
    
    # Convert American odds to decimal multiplier
    if odds >= 0:
        # Positive odds: profit = (odds / 100) * stake
        decimal_odds = 1 + (odds / 100)
    else:
        # Negative odds: profit = (100 / abs(odds)) * stake
        decimal_odds = 1 + (100 / abs(odds))
    
    # EV = (probability * profit) - (1 - probability) * stake
    # For $100 bet: profit = (decimal_odds - 1) * 100, stake = 100
    win_amount = (decimal_odds - 1) * 100
    lose_amount = 100
    
    ev = (probability * win_amount) - ((1 - probability) * lose_amount)
    return round(ev, 2)


def _calculate_no_vig_odds(over_odds: int, under_odds: int) -> dict:
    """
    Calculate no-vig (fair) odds by removing the sportsbook's juice/vig.
    
    Args:
        over_odds: American odds for OVER (e.g., -110)
        under_odds: American odds for UNDER (e.g., -110)
    
    Returns:
        dict with fair_over_prob, fair_under_prob, vig_percent
    """
    # Convert American odds to implied probability
    def american_to_prob(odds: int) -> float:
        if odds >= 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    
    over_prob = american_to_prob(over_odds)
    under_prob = american_to_prob(under_odds)
    
    # Total probability > 1.0 indicates vig
    total_prob = over_prob + under_prob
    vig_percent = (total_prob - 1.0) * 100
    
    # Remove vig by normalizing to 100%
    fair_over_prob = over_prob / total_prob
    fair_under_prob = under_prob / total_prob
    
    return {
        "fair_over_prob": round(fair_over_prob, 4),
        "fair_under_prob": round(fair_under_prob, 4),
        "vig_percent": round(vig_percent, 2)
    }


def _nearest_game_date(db) -> date | None:
    """
    Returns the nearest date (today or tomorrow only) that has
    FanDuel odds lines stored.
    Only looks 1 day ahead — we only want today's or tomorrow's game lines,
    not games further in the future.
    Falls back to today if nothing found.
    """
    for days_ahead in range(2):  # only today or tomorrow
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
    # fallback — find next game date with fanduel lines within 7 days
    for days_ahead in range(2, 8):
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
    stat_type:    Optional[str] = Query(None),
    sportsbook:   Optional[str] = Query('fanduel', description="Sportsbook (default: fanduel)"),
    min_edge_pct: float = Query(3.0, description="Minimum edge % to show"),
    db: Session = Depends(get_db),
):
    """
    THE core endpoint. Compares our projections against real sportsbook lines.
    Returns players where our model disagrees with the book by min_edge_pct or more.
    
    Note: Defaults to FanDuel lines for consistency. Frontend always uses FanDuel.
    """
    today = _nearest_game_date(db)
    games = db.query(Game).filter(Game.date == today).all()
    game_ids = [g.id for g in games]

    if not game_ids:
        return {"edges": [], "message": "No games or lines found in next 3 days"}

    # Build query with optional filters
    lines_query = db.query(OddsLine).filter(OddsLine.game_id.in_(game_ids))
    
    # Only filter by stat_type if provided
    if stat_type:
        lines_query = lines_query.filter(OddsLine.stat_type == stat_type)
    
    # Only filter by sportsbook if provided
    if sportsbook:
        lines_query = lines_query.filter(OddsLine.sportsbook == sportsbook)
    
    lines = lines_query.all()

    if not lines:
        return {
            "edges":   [],
            "message": f"No lines found for stat_type={stat_type or 'all'}, sportsbook={sportsbook or 'all'}. "
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
        # Use the line's stat_type (not the filter parameter)
        proj = project_player(
            db          = db,
            player_id   = ol.player_id,
            stat_type   = ol.stat_type,
            opp_team_id = opp_team_id,
            line        = ol.line,
        )
        if not proj or proj.projected <= 0:
            continue

        # Save projection for accuracy tracking
        save_projection(
            db=db,
            proj=proj,
            game_id=ol.game_id,
            opp_team_id=opp_team_id,
            line=ol.line,
            sportsbook=ol.sportsbook,
        )

        # Only include if edge is meaningful
        if abs(proj.edge_pct or 0) < min_edge_pct:
            continue

        team = db.query(Team).filter(Team.id == player.team_id).first()
        opp  = db.query(Team).filter(Team.id == opp_team_id).first()

        # Calculate streak for this player/stat/line combination
        streak = calculate_streak(
            db=db,
            player_id=player.id,
            stat_type=ol.stat_type,
            line=ol.line,
            limit=10
        )

        # Calculate Expected Value for both OVER and UNDER
        # Probabilities might be decimals (0.65) or percentages (65.0)
        over_prob_decimal = proj.over_prob if proj.over_prob <= 1 else proj.over_prob / 100
        under_prob_decimal = proj.under_prob if proj.under_prob <= 1 else proj.under_prob / 100
        
        over_ev = _calculate_ev(over_prob_decimal, ol.over_odds or -110)
        under_ev = _calculate_ev(under_prob_decimal, ol.under_odds or -110)
        
        # Use EV of the recommended bet
        expected_value = over_ev if proj.recommendation == 'OVER' else under_ev

        # Calculate no-vig fair odds
        no_vig = _calculate_no_vig_odds(ol.over_odds or -110, ol.under_odds or -110)

        results.append({
            "player_id":      player.id,
            "player_name":    player.name,
            "team_abbr":      team.abbreviation if team else "?",
            "opp_abbr":       opp.abbreviation if opp else "?",
            "position":       player.position,
            "stat_type":      ol.stat_type,
            "sportsbook":     ol.sportsbook,
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
            "streak":         streak,
            "expected_value": expected_value,  # EV for recommended bet
            "over_ev":        over_ev,         # EV for OVER
            "under_ev":       under_ev,        # EV for UNDER
            "no_vig_fair_over": no_vig["fair_over_prob"],
            "no_vig_fair_under": no_vig["fair_under_prob"],
            "vig_percent": no_vig["vig_percent"],
        })

    # Sort by absolute edge descending
    results.sort(key=lambda x: abs(x["edge_pct"] or 0), reverse=True)

    return {
        "date":       str(today),
        "stat_type":  stat_type or "all",
        "sportsbook": sportsbook or "all",
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

        # Calculate EV and no-vig for this line
        over_ev = None
        under_ev = None
        expected_value = None
        no_vig_fair_over = None
        no_vig_fair_under = None
        vig_percent = None

        if proj:
            # Calculate EV
            over_prob_decimal = proj.over_prob if proj.over_prob <= 1 else proj.over_prob / 100
            under_prob_decimal = proj.under_prob if proj.under_prob <= 1 else proj.under_prob / 100
            
            over_ev = _calculate_ev(over_prob_decimal, ol.over_odds or -110)
            under_ev = _calculate_ev(under_prob_decimal, ol.under_odds or -110)
            expected_value = over_ev if proj.recommendation == 'OVER' else under_ev

            # Calculate no-vig
            no_vig = _calculate_no_vig_odds(ol.over_odds or -110, ol.under_odds or -110)
            no_vig_fair_over = no_vig["fair_over_prob"]
            no_vig_fair_under = no_vig["fair_under_prob"]
            vig_percent = no_vig["vig_percent"]

        result.append({
            "stat_type":      ol.stat_type,
            "sportsbook":     ol.sportsbook,
            "line":           ol.line,
            "over_odds":      ol.over_odds,
            "under_odds":     ol.under_odds,
            "projected":      proj.projected if proj else None,
            "edge_pct":       proj.edge_pct if proj else None,
            "over_prob":      proj.over_prob if proj else None,
            "under_prob":     proj.under_prob if proj else None,
            "recommendation": proj.recommendation if proj else None,
            "expected_value": expected_value,
            "over_ev":        over_ev,
            "under_ev":       under_ev,
            "no_vig_fair_over": no_vig_fair_over,
            "no_vig_fair_under": no_vig_fair_under,
            "vig_percent":    vig_percent,
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