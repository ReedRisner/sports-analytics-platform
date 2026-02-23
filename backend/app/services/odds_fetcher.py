# backend/app/services/odds_fetcher.py
"""
Odds API fetcher — pulls player prop lines and game lines, saves to DB.

Enhanced to include:
  - Player props: points, rebounds, assists, steals, blocks, threes, PR, PA, RA, PRA
  - Alternate markets for DFS books (includes adjusted demon/goblin-style lines)
  - Game lines: spread, total, moneyline

Credit-efficient design:
  - Checks today first, then up to 3 days ahead for upcoming games
  - Upserts into odds_lines table (no duplicates)
"""

import httpx
import logging
from datetime import date, datetime, timezone, timedelta
from difflib import SequenceMatcher

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.player import Player, Game, OddsLine
from app.config import settings

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ODDS_API_BASE   = "https://api.the-odds-api.com/v4"
# Keep NBA sport for events/game matching.
SPORT           = "basketball_nba"
# FanDuel stays primary for site-wide edges; include DFS books for dedicated pages.
BOOKMAKERS      = "fanduel,prizepicks,underdog"
ODDS_FORMAT     = "american"

# Markets to pull — each adds ~1 credit per event
MARKETS = [
    # Player props
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_blocks",
    "player_steals",
    "player_threes",
    "player_points_rebounds",
    "player_points_assists",
    "player_rebounds_assists",
    "player_points_rebounds_assists",
    # Alternate markets (demons/goblins and adjusted multiplier lines)
    "player_points_alternate",
    "player_rebounds_alternate",
    "player_assists_alternate",
    "player_blocks_alternate",
    "player_steals_alternate",
    "player_threes_alternate",
    "player_points_rebounds_alternate",
    "player_points_assists_alternate",
    "player_rebounds_assists_alternate",
    "player_points_rebounds_assists_alternate",
    # Game lines
    "spreads",
    "totals",
    "h2h",  # moneyline
]

# Map Odds API market name → our stat_type
MARKET_TO_STAT = {
    "player_points":   "points",
    "player_rebounds": "rebounds",
    "player_assists":  "assists",
    "player_blocks":   "blocks",
    "player_steals":   "steals",
    "player_threes":   "threes",
    "player_points_rebounds": "pr",
    "player_points_assists": "pa",
    "player_rebounds_assists": "ra",
    "player_points_rebounds_assists": "pra",
    "player_points_alternate": "points",
    "player_rebounds_alternate": "rebounds",
    "player_assists_alternate": "assists",
    "player_blocks_alternate": "blocks",
    "player_steals_alternate": "steals",
    "player_threes_alternate": "threes",
    "player_points_rebounds_alternate": "pr",
    "player_points_assists_alternate": "pa",
    "player_rebounds_assists_alternate": "ra",
    "player_points_rebounds_assists_alternate": "pra",
    # Game lines (handled separately)
    "spreads": "spread",
    "totals": "total",
    "h2h": "moneyline",
}

# Sportsbooks we care about
TARGET_BOOKS = {"fanduel", "prizepicks", "underdog"}


def _odds_upsert_conflict_config(db: Session) -> tuple[dict, tuple[str, ...]]:
    """
    Build ON CONFLICT args and de-duplication keys for odds_lines upserts.

    Returns:
      - kwargs for SQLAlchemy on_conflict_do_update(...)
      - field names that define uniqueness for the active schema
    """
    unique_constraints = {
        c.get("name")
        for c in inspect(db.bind).get_unique_constraints("odds_lines")
        if c.get("name")
    }

    if "uq_odds_player_game_stat_book_line" in unique_constraints:
        return (
            {"constraint": "uq_odds_player_game_stat_book_line"},
            ("player_id", "game_id", "stat_type", "sportsbook", "line"),
        )

    if "uq_odds_player_game_stat_book" in unique_constraints:
        return (
            {"constraint": "uq_odds_player_game_stat_book"},
            ("player_id", "game_id", "stat_type", "sportsbook"),
        )

    # Fallback for databases where constraints are unnamed but keys exist.
    return (
        {"index_elements": ["player_id", "game_id", "stat_type", "sportsbook", "line"]},
        ("player_id", "game_id", "stat_type", "sportsbook", "line"),
    )


def _dedupe_rows(rows: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
    """Keep only the newest row per active unique key to prevent ON CONFLICT cardinality errors."""
    deduped: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        deduped[key] = row
    return list(deduped.values())


def _compact_error_message(exc: Exception) -> str:
    """Return a concise, user-readable error message without huge SQL payloads."""
    if isinstance(exc, SQLAlchemyError) and getattr(exc, "orig", None) is not None:
        return str(exc.orig)
    return str(exc)


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
    Main entry point. Fetches today's NBA prop lines and game lines, upserts into DB.
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
        "game_lines_saved": 0,
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

            # Find games in next 4 days, preferring the first day with DB matches.
            target_events = []
            target_date   = None
            for days_ahead in range(4):
                check_date  = date.today() + timedelta(days=days_ahead)
                next_date   = check_date + timedelta(days=1)
                check_str   = check_date.isoformat()
                next_str    = next_date.isoformat()
                day_events  = [
                    e for e in events
                    if e.get("commence_time", "").startswith(check_str)
                    or e.get("commence_time", "").startswith(next_str)
                ]
                if not day_events:
                    continue

                matched_events = []
                for event in day_events:
                    game = _find_game(
                        db,
                        event.get("home_team", ""),
                        event.get("away_team", ""),
                        game_date=check_date,
                    )
                    if game:
                        matched_events.append(event)

                if matched_events:
                    target_events = matched_events
                    target_date   = check_date
                    break

                logger.info(
                    "No DB game matches found for %s events on %s — checking next day",
                    len(day_events),
                    check_date,
                )

            if not target_events:
                logger.info("No NBA games with DB matches in the next 4 days — skipping odds fetch")
                summary["errors"].append("No games with DB matches in next 4 days")
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

                # Find matching game in our DB (should already be matchable from pre-filter)
                game = _find_game(db, home_team, away_team, game_date=target_date)
                if not game:
                    logger.warning(f"Could not match game after pre-check: {away_team} @ {home_team}")
                    summary["errors"].append(f"No DB match after pre-check: {away_team} @ {home_team}")
                    continue

                try:
                    props_resp = client.get(
                        f"{ODDS_API_BASE}/sports/{SPORT}/events/{event_id}/odds",
                        params={
                            "apiKey":     api_key,
                            "bookmakers": BOOKMAKERS,
                            "markets":    ",".join(MARKETS),
                            "oddsFormat": ODDS_FORMAT,
                        },
                    )
                    props_resp.raise_for_status()
                    summary["credits_used"] += 1

                    data = props_resp.json()
                    player_lines, game_lines = _parse_and_save(db, game, data)
                    summary["lines_saved"]      += player_lines
                    summary["game_lines_saved"] += game_lines
                    summary["games_processed"]  += 1

                except httpx.HTTPStatusError as e:
                    err = f"{away_team} @ {home_team}: HTTP {e.response.status_code}"
                    logger.error(err)
                    summary["errors"].append(err)

        logger.info(f"Odds fetch complete: {summary}")
        return summary

    except Exception as e:
        compact_error = _compact_error_message(e)
        logger.error("Odds fetch failed: %s", compact_error)
        summary["errors"].append(compact_error)
        return summary

    finally:
        if close_db:
            db.close()


def _find_game(db: Session, home_team: str, away_team: str, game_date: date | None = None) -> Game | None:
    """
    Match Odds API team names to our DB games.
    Checks both target date and day before (UTC vs local date offset).
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


def _parse_and_save(db: Session, game: Game, data: dict) -> tuple[int, int]:
    """
    Parse the Odds API event-odds response and upsert into odds_lines.
    Returns (player_lines_saved, game_lines_saved).
    """
    player_lines_saved = 0
    game_lines_saved = 0
    bookmakers = data.get("bookmakers", [])

    # De-duplicate player prop writes within one API payload to avoid
    # unique-key collisions on (player_id, game_id, stat_type, sportsbook, line).
    pending_rows: dict[tuple[int, int, str, str, float], dict] = {}

    for book in bookmakers:
        book_key = book.get("key", "")
        if book_key not in TARGET_BOOKS:
            continue

        for market in book.get("markets", []):
            market_key = market.get("key", "")
            stat_type = MARKET_TO_STAT.get(market_key)
            if not stat_type:
                continue

            # Handle game lines (spread, total, moneyline) separately
            if stat_type in ["spread", "total", "moneyline"]:
                game_lines_saved += _save_game_line(db, game, book_key, stat_type, market)
                continue

            outcomes = market.get("outcomes", [])

            # Build dict: (player_name, line) -> line data for this market.
            # This preserves all alternate adjusted lines for DFS books.
            player_lines: dict[tuple[str, float], dict] = {}
            for outcome in outcomes:
                name = outcome.get("description", "")  # player name
                side = outcome.get("name", "")         # "Over" or "Under"
                point = outcome.get("point")            # line value
                price = outcome.get("price")            # American odds

                if not name or point is None:
                    continue

                line_key = (name, float(point))
                if line_key not in player_lines:
                    player_lines[line_key] = {
                        "point": float(point),
                        "over_odds": None,
                        "under_odds": None,
                    }

                if side == "Over":
                    player_lines[line_key]["over_odds"] = price
                elif side == "Under":
                    player_lines[line_key]["under_odds"] = price

            for (odds_name, _line_point), line_data in player_lines.items():
                player = _find_player(db, odds_name)
                if not player:
                    continue

                line = line_data.get("point")
                over_odds = line_data.get("over_odds")
                under_odds = line_data.get("under_odds")

                if line is None:
                    continue

                # DFS books sometimes omit prices on adjusted lines.
                if over_odds is None:
                    over_odds = -119
                if under_odds is None:
                    under_odds = -119

                row_key = (player.id, game.id, stat_type, book_key, float(line))

                pending_rows[row_key] = {
                    "player_id": player.id,
                    "game_id": game.id,
                    "stat_type": stat_type,
                    "sportsbook": book_key,
                    "line": float(line),
                    "over_odds": over_odds,
                    "under_odds": under_odds,
                    "fetched_at": datetime.now(timezone.utc),
                }

    if pending_rows:
        rows = [dict(row) for row in pending_rows.values()]

        conflict_kwargs, conflict_key_fields = _odds_upsert_conflict_config(db)
        rows = _dedupe_rows(rows, conflict_key_fields)

        insert_stmt = pg_insert(OddsLine).values(rows)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            **conflict_kwargs,
            set_={
                "line": insert_stmt.excluded.line,
                "over_odds": insert_stmt.excluded.over_odds,
                "under_odds": insert_stmt.excluded.under_odds,
                "fetched_at": insert_stmt.excluded.fetched_at,
            },
        )
        db.execute(upsert_stmt)
        player_lines_saved = len(rows)

    db.commit()
    return player_lines_saved, game_lines_saved


def _save_game_line(db: Session, game: Game, book_key: str, stat_type: str, market: dict) -> int:
    """
    Save game lines (spread, total, moneyline) to odds_lines table.
    Uses player_id = NULL to indicate these are game lines, not player props.
    Stores both home and away in a single record.
    """
    from app.models.player import Team
    
    outcomes = market.get("outcomes", [])
    
    if stat_type == "spread":
        # Spread has two outcomes: home and away
        home_spread = None
        away_spread = None
        home_odds = None
        away_odds = None
        
        for outcome in outcomes:
            team_name = outcome.get("name", "")
            point = outcome.get("point")  # e.g., -3.5 for favorite
            price = outcome.get("price")  # e.g., -110
            
            if point is None:
                continue
            
            # Determine if this is home or away team spread
            is_home = _is_home_team(db, game, team_name)
            
            if is_home:
                home_spread = point
                home_odds = price
            else:
                away_spread = point
                away_odds = price
        
        # Save single record with both home and away
        if home_spread is not None and away_spread is not None:
            existing = db.query(OddsLine).filter(
                OddsLine.player_id == None,
                OddsLine.game_id == game.id,
                OddsLine.stat_type == "spread",
                OddsLine.sportsbook == book_key,
            ).first()
            
            if existing:
                existing.line = home_spread  # Use home spread as primary
                existing.over_odds = home_odds
                existing.under_odds = away_odds
                existing.fetched_at = datetime.now(timezone.utc)
            else:
                db.add(OddsLine(
                    player_id=None,
                    game_id=game.id,
                    stat_type="spread",
                    sportsbook=book_key,
                    line=home_spread,
                    over_odds=home_odds,
                    under_odds=away_odds,
                ))
            db.commit()
            return 1
    
    elif stat_type == "total":
        # Total has over/under
        total_line = None
        over_odds = None
        under_odds = None
        
        for outcome in outcomes:
            name = outcome.get("name", "")
            point = outcome.get("point")
            price = outcome.get("price")
            
            if point is not None:
                total_line = point
                if name == "Over":
                    over_odds = price
                elif name == "Under":
                    under_odds = price
        
        if total_line is not None:
            existing = db.query(OddsLine).filter(
                OddsLine.player_id == None,
                OddsLine.game_id == game.id,
                OddsLine.stat_type == "total",
                OddsLine.sportsbook == book_key,
            ).first()
            
            if existing:
                existing.line = total_line
                existing.over_odds = over_odds
                existing.under_odds = under_odds
                existing.fetched_at = datetime.now(timezone.utc)
            else:
                db.add(OddsLine(
                    player_id=None,
                    game_id=game.id,
                    stat_type="total",
                    sportsbook=book_key,
                    line=total_line,
                    over_odds=over_odds,
                    under_odds=under_odds,
                ))
            db.commit()
            return 1
    
    elif stat_type == "moneyline":
        # Moneyline has home and away odds
        home_odds = None
        away_odds = None
        
        for outcome in outcomes:
            team_name = outcome.get("name", "")
            price = outcome.get("price")
            
            is_home = _is_home_team(db, game, team_name)
            
            if is_home:
                home_odds = price
            else:
                away_odds = price
        
        # Save single record with both home and away
        if home_odds is not None and away_odds is not None:
            existing = db.query(OddsLine).filter(
                OddsLine.player_id == None,
                OddsLine.game_id == game.id,
                OddsLine.stat_type == "moneyline",
                OddsLine.sportsbook == book_key,
            ).first()
            
            if existing:
                existing.over_odds = home_odds
                existing.under_odds = away_odds
                existing.fetched_at = datetime.now(timezone.utc)
            else:
                db.add(OddsLine(
                    player_id=None,
                    game_id=game.id,
                    stat_type="moneyline",
                    sportsbook=book_key,
                    line=0,  # No line for moneyline
                    over_odds=home_odds,
                    under_odds=away_odds,
                ))
            db.commit()
            return 1
    
    return 0

def _is_home_team(db: Session, game: Game, team_name: str) -> bool:
    """Check if team_name matches the home team for this game."""
    from app.models.player import Team
    
    home_team = db.query(Team).filter(Team.id == game.home_team_id).first()
    if not home_team:
        return False
    
    return SequenceMatcher(None, _normalize(home_team.name), _normalize(team_name)).ratio() >= 0.80


# ── Standalone runner ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    print("Fetching today's NBA odds...")
    result = fetch_todays_odds()
    print(f"\nResult:")
    print(f"  Games processed:    {result['games_processed']}")
    print(f"  Player lines saved: {result['lines_saved']}")
    print(f"  Game lines saved:   {result['game_lines_saved']}")
    print(f"  Credits used:       {result['credits_used']}")
    if result["errors"]:
        print(f"  Errors:             {result['errors']}")
