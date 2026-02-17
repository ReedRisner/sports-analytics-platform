# backend/app/services/odds_fetcher.py
"""
Odds API fetcher — pulls NBA player prop lines and saves to the DB.

Credit-efficient design for 500 credits/month:
  - Checks today first, then up to 3 days ahead for upcoming games
  - Only pulls 3 markets: player_points, player_rebounds, player_assists
  - Upserts into odds_lines table (no duplicates)
  - Scheduled twice daily at midnight and noon PST (08:00 and 20:00 UTC)

Odds API cost breakdown:
  - 1 request to get upcoming events list (1 credit)
  - 1 request per game for props (~1 credit/game)
  - 5 games/day × 2 fetches × ~2 credits = ~20 credits/day
  - Well within 500/month limit
"""

import httpx
import logging
from datetime import date, datetime, timezone, timedelta
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.player import Player, Game, OddsLine
from app.config import settings

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ODDS_API_BASE   = "https://api.the-odds-api.com/v4"
SPORT           = "basketball_nba"
REGIONS         = "us"         # us = FanDuel, DraftKings, BetMGM, etc.
ODDS_FORMAT     = "american"

# Markets to pull — each adds ~1 credit per event, keep this list short
MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
]

# Map Odds API market name → our stat_type
MARKET_TO_STAT = {
    "player_points":   "points",
    "player_rebounds": "rebounds",
    "player_assists":  "assists",
}

# Sportsbooks we care about — filter to just these to keep response small
TARGET_BOOKS = {
    "fanduel", "draftkings", "betmgm", "bet365",
    "williamhill_us", "pointsbetus", "bovada",
}


# ── Name matching ─────────────────────────────────────────────────────────────
def _normalize(name: str) -> str:
    """Lowercase, strip accents-ish, remove punctuation for fuzzy matching."""
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.lower().strip()


def _find_player(db: Session, odds_name: str) -> Player | None:
    """
    Match an Odds API player name to a DB player.
    Tries exact match first, then fuzzy match on normalized names.
    Caches all active players to avoid N+1 queries.
    """
    normalized = _normalize(odds_name)

    # Load all active players once per call (cached via SQLAlchemy session)
    players = db.query(Player).filter(Player.is_active == True).all()

    # 1. Exact normalized match
    for p in players:
        if _normalize(p.name) == normalized:
            return p

    # 2. Fuzzy match — threshold 0.85 to avoid false positives
    best_score  = 0.0
    best_player = None
    for p in players:
        score = SequenceMatcher(None, _normalize(p.name), normalized).ratio()
        if score > best_score:
            best_score  = score
            best_player = p

def _find_player(db: Session, odds_name: str) -> Player | None:
    """
    Match an Odds API player name to a DB player.
    Tries exact match first, then fuzzy match, then last-name fallback.
    """
    normalized = _normalize(odds_name)

    # Load all active players once per call
    players = db.query(Player).filter(Player.is_active == True).all()

    # 1. Exact normalized match
    for p in players:
        if _normalize(p.name) == normalized:
            return p

    # 2. Fuzzy match — 0.82 threshold catches "Nic Claxton" vs "Nicolas Claxton"
    best_score  = 0.0
    best_player = None
    for p in players:
        score = SequenceMatcher(None, _normalize(p.name), normalized).ratio()
        if score > best_score:
            best_score  = score
            best_player = p

    if best_score >= 0.82:
        return best_player

    # 3. Last-name + first-initial fallback for suffixes like "Ron Holland II"
    odds_parts = normalized.split()
    if len(odds_parts) >= 2:
        odds_last  = odds_parts[-1]
        odds_first = odds_parts[0][0] if odds_parts[0] else ""
        for p in players:
            db_parts = _normalize(p.name).split()
            if len(db_parts) >= 2:
                db_last  = db_parts[-1]
                db_first = db_parts[0][0] if db_parts[0] else ""
                if odds_last == db_last and odds_first == db_first:
                    return p

    logger.warning(f"Could not match odds player: '{odds_name}' (best score: {best_score:.2f})")
    return None


# ── Core fetch logic ──────────────────────────────────────────────────────────
def fetch_todays_odds(db: Session | None = None) -> dict:
    """
    Main entry point. Fetches today's NBA prop lines and upserts into DB.
    Returns a summary dict: {games_processed, lines_saved, credits_used, errors}
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    summary = {
        "fetched_at":      datetime.now(timezone.utc).isoformat(),
        "games_processed": 0,
        "lines_saved":     0,
        "credits_used":    0,
        "errors":          [],
    }

    try:
        api_key = settings.ODDS_API_KEY
        if not api_key:
            raise ValueError("ODDS_API_KEY is not set in .env")

        with httpx.Client(timeout=30) as client:

            # ── Step 1: Get today's NBA events ────────────────────────────────
            events_resp = client.get(
                f"{ODDS_API_BASE}/sports/{SPORT}/events",
                params={"apiKey": api_key, "dateFormat": "iso"},
            )
            events_resp.raise_for_status()

            # Track credits used
            remaining = events_resp.headers.get("x-requests-remaining", "?")
            used      = events_resp.headers.get("x-requests-used", "?")
            logger.info(f"Odds API credits — used: {used}, remaining: {remaining}")
            summary["credits_used"] += 1

            events = events_resp.json()

            # The Odds API returns commence_time in UTC. A 7pm EST game on
            # Feb 19 = midnight UTC Feb 20, so the API may report it one day
            # ahead of our DB date. For each candidate day we collect events
            # on that UTC date AND the next UTC date, then _find_game handles
            # matching to the correct local DB date.
            target_events = []
            target_date   = None
            for days_ahead in range(4):   # 0=today, 1=tomorrow, 2, 3
                check_date  = date.today() + timedelta(days=days_ahead)
                next_date   = check_date + timedelta(days=1)
                check_str   = check_date.isoformat()
                next_str    = next_date.isoformat()
                day_events  = [
                    e for e in events
                    if e.get("commence_time", "").startswith(check_str)
                    or e.get("commence_time", "").startswith(next_str)
                ]
                if day_events:
                    target_events = day_events
                    target_date   = check_date
                    break

            if not target_events:
                logger.info("No NBA games in the next 3 days — skipping odds fetch")
                summary["errors"].append("No games in next 3 days")
                return summary

            if target_date == date.today():
                logger.info(f"Found {len(target_events)} NBA games today")
            else:
                days_out = (target_date - date.today()).days
                logger.info(f"No games today — found {len(target_events)} games on {target_date} ({days_out} day(s) ahead)")

            summary["target_date"] = str(target_date)

            # ── Step 2: Fetch props per event ─────────────────────────────────
            for event in target_events:
                event_id   = event["id"]
                home_team  = event.get("home_team", "")
                away_team  = event.get("away_team", "")

                # Find matching game in our DB
                game = _find_game(db, home_team, away_team, game_date=target_date)
                if not game:
                    logger.warning(f"Could not match game: {away_team} @ {home_team}")
                    summary["errors"].append(f"No DB match: {away_team} @ {home_team}")
                    continue

                try:
                    props_resp = client.get(
                        f"{ODDS_API_BASE}/sports/{SPORT}/events/{event_id}/odds",
                        params={
                            "apiKey":     api_key,
                            "regions":    REGIONS,
                            "markets":    ",".join(MARKETS),
                            "oddsFormat": ODDS_FORMAT,
                        },
                    )
                    props_resp.raise_for_status()
                    summary["credits_used"] += 1

                    data = props_resp.json()
                    lines_saved = _parse_and_save(db, game, data)
                    summary["lines_saved"]     += lines_saved
                    summary["games_processed"] += 1

                except httpx.HTTPStatusError as e:
                    err = f"{away_team} @ {home_team}: HTTP {e.response.status_code}"
                    logger.error(err)
                    summary["errors"].append(err)

        logger.info(f"Odds fetch complete: {summary}")
        return summary

    except Exception as e:
        logger.exception(f"Odds fetch failed: {e}")
        summary["errors"].append(str(e))
        return summary

    finally:
        if close_db:
            db.close()


def _find_game(db: Session, home_team: str, away_team: str, game_date: date | None = None) -> Game | None:
    """
    Match Odds API team names to our DB games.

    The Odds API returns commence_time in UTC. A game that tips at 7pm EST
    on Feb 19 has a UTC time of midnight Feb 20, so the Odds API reports it
    as Feb 20 while our DB stores it as Feb 19 (local date). We check both
    the target date AND the day before to handle this timezone shift.
    """
    from app.models.player import Team
    from datetime import timedelta

    game_date = game_date or date.today()

    # Check target date first, then the day before (UTC vs local date offset)
    dates_to_check = [game_date, game_date - timedelta(days=1)]

    for check_date in dates_to_check:
        games = db.query(Game).filter(Game.date == check_date).all()

        for game in games:
            home = db.query(Team).filter(Team.id == game.home_team_id).first()
            away = db.query(Team).filter(Team.id == game.away_team_id).first()
            if not home or not away:
                continue

            home_score = SequenceMatcher(None,
                _normalize(home.name), _normalize(home_team)).ratio()
            away_score = SequenceMatcher(None,
                _normalize(away.name), _normalize(away_team)).ratio()

            if home_score >= 0.80 and away_score >= 0.80:
                return game

    return None


def _parse_and_save(db: Session, game: Game, data: dict) -> int:
    """
    Parse the Odds API event-odds response and upsert into odds_lines.
    Returns number of lines saved.
    """
    saved = 0
    bookmakers = data.get("bookmakers", [])

    for book in bookmakers:
        book_key = book.get("key", "")
        if book_key not in TARGET_BOOKS:
            continue

        for market in book.get("markets", []):
            market_key = market.get("key", "")
            stat_type  = MARKET_TO_STAT.get(market_key)
            if not stat_type:
                continue

            # Each outcome is one player's line
            # Odds API groups over/under as two outcomes with same description
            outcomes = market.get("outcomes", [])

            # Build dict: player_name → {over_price, under_price, point}
            player_lines: dict[str, dict] = {}
            for outcome in outcomes:
                name   = outcome.get("description", "")   # player name
                side   = outcome.get("name", "")           # "Over" or "Under"
                point  = outcome.get("point")              # the line value
                price  = outcome.get("price")              # American odds

                if not name or point is None:
                    continue

                if name not in player_lines:
                    player_lines[name] = {"point": point}

                if side == "Over":
                    player_lines[name]["over_odds"] = price
                elif side == "Under":
                    player_lines[name]["under_odds"] = price

            # Match each player to our DB and upsert
            for odds_name, line_data in player_lines.items():
                player = _find_player(db, odds_name)
                if not player:
                    continue

                line       = line_data.get("point")
                over_odds  = line_data.get("over_odds")
                under_odds = line_data.get("under_odds")

                if line is None:
                    continue

                # Upsert — update if exists, insert if not
                existing = db.query(OddsLine).filter(
                    OddsLine.player_id  == player.id,
                    OddsLine.game_id    == game.id,
                    OddsLine.stat_type  == stat_type,
                    OddsLine.sportsbook == book_key,
                ).first()

                if existing:
                    existing.line       = line
                    existing.over_odds  = over_odds
                    existing.under_odds = under_odds
                    existing.fetched_at = datetime.now(timezone.utc)
                else:
                    db.add(OddsLine(
                        player_id   = player.id,
                        game_id     = game.id,
                        stat_type   = stat_type,
                        sportsbook  = book_key,
                        line        = line,
                        over_odds   = over_odds,
                        under_odds  = under_odds,
                    ))
                saved += 1

    db.commit()
    return saved


# ── Standalone runner ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Fetching today's NBA odds...")
    result = fetch_todays_odds()
    print(f"\nResult:")
    print(f"  Games processed: {result['games_processed']}")
    print(f"  Lines saved:     {result['lines_saved']}")
    print(f"  Credits used:    {result['credits_used']}")
    if result["errors"]:
        print(f"  Errors:          {result['errors']}")