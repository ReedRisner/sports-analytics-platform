# backend/app/services/nba_fetcher.py
import time
import requests
from nba_api.stats.static import teams as nba_teams_static, players as nba_players_static
from app.database import SessionLocal
from app.models.player import Team, Player, PlayerGameStats, Game

# ── Session with full browser headers ───────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    'Host': 'stats.nba.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Connection': 'keep-alive',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
})

# ── Confirmed working URL from endpoint docs ─────────────────────────────────
# Uses playergamelogs (plural) — returns ALL players in one request
# Season format: "2024-25" or "2025-26"
GAMELOGS_URL = "https://stats.nba.com/stats/playergamelogs"


# ── Helpers ──────────────────────────────────────────────────────────────────
def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(val, default=0):
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default

def fetch_with_retry(url, params, retries=5, wait=20):
    """Fetch URL with params, retry on timeout."""
    for attempt in range(1, retries + 1):
        try:
            print(f"  Attempt {attempt}/{retries}...")
            resp = SESSION.get(url, params=params, timeout=90)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            print(f"  Timed out. Waiting {wait}s...")
            time.sleep(wait)
        except requests.exceptions.RequestException as e:
            print(f"  Error: {e}. Waiting {wait}s...")
            time.sleep(wait)
    raise Exception(f"Failed after {retries} attempts.")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Seed all 30 teams
# ─────────────────────────────────────────────────────────────────────────────
def seed_teams():
    db = SessionLocal()
    try:
        teams = nba_teams_static.get_teams()
        added = 0
        for t in teams:
            existing = db.query(Team).filter(Team.id == t['id']).first()
            if not existing:
                db.add(Team(
                    id=t['id'],
                    name=t['full_name'],
                    abbreviation=t['abbreviation']
                ))
                added += 1
        db.commit()
        print(f"  ✓ {added} new teams added ({len(teams)} total)")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Seed all active players
# ─────────────────────────────────────────────────────────────────────────────
def seed_players():
    db = SessionLocal()
    try:
        all_players = nba_players_static.get_active_players()
        added = 0
        for p in all_players:
            existing = db.query(Player).filter(Player.id == p['id']).first()
            if not existing:
                db.add(Player(
                    id=p['id'],
                    name=p['full_name'],
                    is_active=True
                ))
                added += 1
        db.commit()
        print(f"  ✓ {added} new players added ({len(all_players)} total active)")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Fetch all game logs for a season
# ─────────────────────────────────────────────────────────────────────────────
def fetch_player_gamelogs(season="2025-26"):
    """
    Pulls all player game logs for the given season.
    Uses 2025-26 by default since it's the current season.
    """
    db = SessionLocal()
    try:
        params = {
            "Season": season,
            "SeasonType": "Regular Season",
            "LeagueID": "00",
        }

        print(f"  Fetching {season} game logs from NBA API...")
        print(f"  URL: {GAMELOGS_URL}")
        print(f"  Params: {params}")

        data = fetch_with_retry(GAMELOGS_URL, params=params, retries=5, wait=20)

        # ── Parse response structure ─────────────────────────────────────────
        # Based on confirmed endpoint: data['resultSets'][0]
        result_sets = data.get('resultSets', [])
        if not result_sets:
            print("  ✗ No resultSets in response. Full response keys:", list(data.keys()))
            return

        result_set = result_sets[0]
        col_names  = result_set['headers']
        rows       = result_set['rowSet']

        print(f"  ✓ Got {len(rows)} rows")
        print(f"  Columns available: {col_names[:10]}...")  # show first 10 cols

        if len(rows) == 0:
            print("  ⚠ Zero rows — try season='2025-26' if using 2025-26")
            return

        # Helper to get value by column name
        def val(row, col, default=0):
            try:
                idx = col_names.index(col)
                v = row[idx]
                return v if v is not None else default
            except (ValueError, IndexError):
                return default

        saved      = 0
        game_cache = {}
        team_cache = {}

        for row in rows:
            player_name   = val(row, 'PLAYER_NAME', '')
            nba_player_id = safe_int(val(row, 'PLAYER_ID'))
            nba_team_id   = safe_int(val(row, 'TEAM_ID'))
            game_date_str = str(val(row, 'GAME_DATE', ''))
            matchup       = str(val(row, 'MATCHUP', ''))

            if not player_name:
                continue

            # ── Resolve team ─────────────────────────────────────────────────
            if nba_team_id not in team_cache:
                team_cache[nba_team_id] = db.query(Team).filter(
                    Team.id == nba_team_id
                ).first()
            team = team_cache[nba_team_id]

            # ── Resolve player ───────────────────────────────────────────────
            player = db.query(Player).filter(Player.id == nba_player_id).first()
            if not player:
                player = Player(id=nba_player_id, name=player_name, is_active=True)
                db.add(player)
                db.flush()
            if team and player.team_id != team.id:
                player.team_id = team.id

            # ── Resolve game ─────────────────────────────────────────────────
            # GAME_DATE from this endpoint: "2017-04-12T00:00:00" format
            game_date_clean = game_date_str[:10] if game_date_str else None
            game_key = f"{game_date_clean}_{matchup}"

            if game_key not in game_cache:
                is_home = 'vs.' in matchup
                game = Game(
                    date=game_date_clean,
                    home_team_id=team.id if (team and is_home) else None,
                    away_team_id=team.id if (team and not is_home) else None,
                    status='final'
                )
                db.add(game)
                db.flush()
                game_cache[game_key] = game
            game = game_cache[game_key]

            # ── Parse stats ──────────────────────────────────────────────────
            points   = safe_int(val(row, 'PTS'))
            rebounds = safe_int(val(row, 'REB'))
            assists  = safe_int(val(row, 'AST'))
            fg3m     = safe_int(val(row, 'FG3M'))
            fg3a     = safe_int(val(row, 'FG3A'))

            # MIN is a float in this endpoint (e.g. 20.88) — no colon parsing needed
            minutes = safe_float(val(row, 'MIN'))

            db.add(PlayerGameStats(
                player_id         = player.id,
                game_id           = game.id,
                minutes           = minutes,
                points            = points,
                rebounds          = rebounds,
                assists           = assists,
                fg3m              = fg3m,
                fg3a              = fg3a,
                fg3_pct           = round(fg3m / fg3a, 3) if fg3a > 0 else 0.0,
                pra               = points + rebounds + assists,
                pr                = points + rebounds,
                pa                = points + assists,
                ra                = rebounds + assists,
                usage_rate        = safe_float(val(row, 'USG_PCT')),
                true_shooting_pct = safe_float(val(row, 'TS_PCT')),
                fantasy_points    = safe_float(val(row, 'NBA_FANTASY_PTS')),
            ))
            saved += 1

            if saved % 200 == 0:
                db.commit()
                print(f"  Saved {saved} / {len(rows)} rows...")

        db.commit()
        print(f"  ✓ Done — saved {saved} stat lines")

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error: {e}")
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  NBA Data Fetcher")
    print("=" * 50)

    print("\n[1/3] Seeding teams...")
    seed_teams()

    print("\n[2/3] Seeding players...")
    seed_players()

    print("\n[3/3] Fetching game logs...")
    # 2024-25 is the safe default — confirmed season with data
    # Change to "2025-26" once that season is underway
    fetch_player_gamelogs(season="2025-26")

    print("\n" + "=" * 50)
    print("  Done! In TablePlus press Ctrl+R to refresh.")
    print("  teams             → 30 rows")
    print("  players           → rows with team_id filled")
    print("  games             → one row per game")
    print("  player_game_stats → thousands of rows")
    print("=" * 50)