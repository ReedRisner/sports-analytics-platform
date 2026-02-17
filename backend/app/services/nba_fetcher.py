# backend/app/services/nba_fetcher.py
import time
import requests
from nba_api.stats.static import teams as nba_teams_static, players as nba_players_static
from app.database import SessionLocal
from app.models.player import Team, Player, PlayerGameStats, Game

# ── Exact headers that returned 200 in your test ─────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://www.nba.com/',
})

GAMELOGS_URL = "https://stats.nba.com/stats/playergamelogs"


# ── Helpers ───────────────────────────────────────────────────────────────────
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
# STEP 3 — Fetch all game logs
# ─────────────────────────────────────────────────────────────────────────────
def fetch_player_gamelogs(season="2025-26"):
    db = SessionLocal()
    try:
        params = {
            "Season": season,
            "SeasonType": "Regular Season",
            "LeagueID": "00",
        }

        print(f"  Contacting NBA API for {season}...")
        resp = SESSION.get(GAMELOGS_URL, params=params, timeout=60)
        resp.raise_for_status()

        data       = resp.json()
        result_set = data['resultSets'][0]
        col_names  = result_set['headers']
        rows       = result_set['rowSet']

        print(f"  ✓ Got {len(rows)} rows")

        if len(rows) == 0:
            print("  ⚠ No rows returned for this season.")
            return

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

            # ── Team ─────────────────────────────────────────────────────────
            if nba_team_id not in team_cache:
                team_cache[nba_team_id] = db.query(Team).filter(
                    Team.id == nba_team_id
                ).first()
            team = team_cache[nba_team_id]

            # ── Player ───────────────────────────────────────────────────────
            player = db.query(Player).filter(Player.id == nba_player_id).first()
            if not player:
                player = Player(id=nba_player_id, name=player_name, is_active=True)
                db.add(player)
                db.flush()
            if team and player.team_id != team.id:
                player.team_id = team.id

            # ── Game ─────────────────────────────────────────────────────────
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

            # ── Stats ─────────────────────────────────────────────────────────
            points   = safe_int(val(row, 'PTS'))
            rebounds = safe_int(val(row, 'REB'))
            assists  = safe_int(val(row, 'AST'))
            fg3m     = safe_int(val(row, 'FG3M'))
            fg3a     = safe_int(val(row, 'FG3A'))
            minutes  = safe_float(val(row, 'MIN'))

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

            if saved % 500 == 0:
                db.commit()
                print(f"  Saved {saved} / {len(rows)} rows...")

        db.commit()
        print(f"  ✓ Done — saved {saved} stat lines to database")

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

    print("\n[3/3] Fetching 2024-25 game logs...")
    fetch_player_gamelogs(season="2025-26")

    print("\n" + "=" * 50)
    print("  Done! Press Ctrl+R in TablePlus to refresh.")
    print("  teams             → 30 rows")
    print("  players           → rows with team_id filled")
    print("  games             → one row per game")
    print("  player_game_stats → thousands of rows")
    print("=" * 50)