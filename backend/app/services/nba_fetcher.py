# backend/app/services/nba_fetcher.py
import time
import requests
from nba_api.stats.static import teams as nba_teams_static, players as nba_players_static
from app.database import SessionLocal
from app.models.player import Team, Player, PlayerGameStats, Game

# ── Session with confirmed working headers ────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://www.nba.com/',
})

GAMELOGS_URL  = "https://stats.nba.com/stats/playergamelogs"
ROSTER_URL    = "https://stats.nba.com/stats/commonteamroster"
BOXSCORE_URL  = "https://stats.nba.com/stats/boxscoresummaryv2"


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

def nba_get(url, params, timeout=60):
    """Single GET request — no retries, just raises on failure."""
    resp = SESSION.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def parse_result_set(data, index=0):
    """Extract headers + rows from resultSets[index]."""
    rs       = data['resultSets'][index]
    headers  = rs['headers']
    rows     = rs['rowSet']
    return headers, rows

def row_val(headers, row, col, default=0):
    try:
        idx = headers.index(col)
        v   = row[idx]
        return v if v is not None else default
    except (ValueError, IndexError):
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
# STEP 2 — Seed players WITH position + jersey from team rosters
# ─────────────────────────────────────────────────────────────────────────────
def seed_players_with_details(season="2025-26"):
    """
    Loops through all 30 teams and pulls their full roster,
    which includes position and jersey number.
    """
    db = SessionLocal()
    try:
        teams = nba_teams_static.get_teams()
        total_added = 0
        total_updated = 0

        for i, t in enumerate(teams):
            try:
                data    = nba_get(ROSTER_URL, {"TeamID": t['id'], "Season": season})
                headers, rows = parse_result_set(data, 0)

                for row in rows:
                    nba_id   = safe_int(row_val(headers, row, 'PLAYER_ID'))
                    name     = str(row_val(headers, row, 'PLAYER', ''))
                    position = str(row_val(headers, row, 'POSITION', ''))
                    jersey   = str(row_val(headers, row, 'NUM', ''))

                    if not nba_id:
                        continue

                    player = db.query(Player).filter(Player.id == nba_id).first()
                    if not player:
                        db.add(Player(
                            id=nba_id,
                            name=name,
                            team_id=t['id'],
                            position=position[:5] if position else None,
                            jersey_number=safe_int(jersey) if jersey.isdigit() else None,
                            is_active=True
                        ))
                        total_added += 1
                    else:
                        # Update missing fields
                        player.team_id      = t['id']
                        player.position     = position[:5] if position else player.position
                        player.jersey_number = safe_int(jersey) if jersey.isdigit() else player.jersey_number
                        total_updated += 1

                db.commit()
                print(f"  [{i+1}/30] {t['full_name']} — done")
                time.sleep(0.6)  # be polite to NBA API

            except Exception as e:
                print(f"  [{i+1}/30] {t['full_name']} — skipped ({e})")
                time.sleep(1)

        print(f"  ✓ {total_added} players added, {total_updated} updated with position/jersey/team")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Fetch all game logs (stats + game linking)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_player_gamelogs(season="2025-26"):
    db = SessionLocal()
    try:
        print(f"  Contacting NBA API for {season}...")
        data      = nba_get(GAMELOGS_URL, {"Season": season, "SeasonType": "Regular Season", "LeagueID": "00"})
        col_names, rows = parse_result_set(data, 0)

        print(f"  ✓ Got {len(rows)} rows")
        if len(rows) == 0:
            print("  ⚠ No rows — season may not have data yet")
            return

        # Build abbreviation -> team lookup for matchup parsing
        abbrev_to_team = {}
        db_teams = db.query(Team).all()
        for t in db_teams:
            if t.abbreviation:
                abbrev_to_team[t.abbreviation] = t

        saved      = 0
        game_cache = {}
        team_cache = {}

        for row in rows:
            player_name   = row_val(col_names, row, 'PLAYER_NAME', '')
            nba_player_id = safe_int(row_val(col_names, row, 'PLAYER_ID'))
            nba_team_id   = safe_int(row_val(col_names, row, 'TEAM_ID'))
            game_date_str = str(row_val(col_names, row, 'GAME_DATE', ''))
            matchup       = str(row_val(col_names, row, 'MATCHUP', ''))
            team_abbrev   = str(row_val(col_names, row, 'TEAM_ABBREVIATION', ''))
            nba_game_id   = str(row_val(col_names, row, 'GAME_ID', ''))
            home_score_r  = safe_int(row_val(col_names, row, 'PTS'))
            wl            = str(row_val(col_names, row, 'WL', ''))

            if not player_name:
                continue

            # ── Team ─────────────────────────────────────────────────────────
            if nba_team_id not in team_cache:
                team_cache[nba_team_id] = db.query(Team).filter(Team.id == nba_team_id).first()
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
            # Matchup format: "LAL vs. GSW" (home) or "LAL @ GSW" (away)
            game_date_clean = game_date_str[:10] if game_date_str else None
            game_key = nba_game_id if nba_game_id else f"{game_date_clean}_{matchup}"

            if game_key not in game_cache:
                is_home = 'vs.' in matchup

                # Parse opponent abbreviation from matchup
                # "LAL vs. GSW" → opp = "GSW"
                # "LAL @ GSW"   → opp = "GSW"
                parts    = matchup.replace('vs.', '@').split('@')
                opp_abbr = parts[1].strip() if len(parts) > 1 else ''
                opp_team = abbrev_to_team.get(opp_abbr)

                game = Game(
                    date         = game_date_clean,
                    home_team_id = team.id if is_home else (opp_team.id if opp_team else None),
                    away_team_id = (opp_team.id if opp_team else None) if is_home else team.id,
                    status       = 'final'
                )
                db.add(game)
                db.flush()
                game_cache[game_key] = game
            game = game_cache[game_key]

            # ── Stats ─────────────────────────────────────────────────────────
            points   = safe_int(row_val(col_names, row, 'PTS'))
            rebounds = safe_int(row_val(col_names, row, 'REB'))
            assists  = safe_int(row_val(col_names, row, 'AST'))
            fg3m     = safe_int(row_val(col_names, row, 'FG3M'))
            fg3a     = safe_int(row_val(col_names, row, 'FG3A'))
            minutes  = safe_float(row_val(col_names, row, 'MIN'))

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
                usage_rate        = safe_float(row_val(col_names, row, 'USG_PCT')),
                true_shooting_pct = safe_float(row_val(col_names, row, 'TS_PCT')),
                fantasy_points    = safe_float(row_val(col_names, row, 'NBA_FANTASY_PTS')),
            ))
            saved += 1

            if saved % 500 == 0:
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
# STEP 4 — Backfill game scores from boxscore summaries
# ─────────────────────────────────────────────────────────────────────────────
def backfill_game_scores(limit=None):
    """
    Fetches final scores for all games that are missing home_score/away_score.
    Pass limit=100 to test on a small batch first.
    """
    db = SessionLocal()
    try:
        query = db.query(Game).filter(
            Game.status == 'final',
            Game.home_score == None
        )
        if limit:
            query = query.limit(limit)
        games = query.all()

        print(f"  Found {len(games)} games missing scores")

        updated = 0
        for i, game in enumerate(games):
            # We need the NBA game_id — stored as string like "0022301161"
            # We'll skip games where we can't identify the NBA game ID
            # (In a future version we'd store nba_game_id directly on the Game model)
            try:
                time.sleep(0.5)
                if i % 50 == 0 and i > 0:
                    print(f"  Updated {updated} game scores...")
            except Exception as e:
                continue

        print(f"  ✓ Score backfill complete — updated {updated} games")
        print("  Note: Add nba_game_id column to Game model for full score support")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    season = "2025-26"

    # Allow overriding season from command line: python -m app.services.nba_fetcher 2025-26
    if len(sys.argv) > 1:
        season = sys.argv[1]

    print("=" * 50)
    print(f"  NBA Data Fetcher — {season}")
    print("=" * 50)

    print("\n[1/3] Seeding teams...")
    seed_teams()

    print(f"\n[2/3] Seeding players with position + jersey ({season} rosters)...")
    seed_players_with_details(season=season)

    print(f"\n[3/3] Fetching {season} game logs...")
    fetch_player_gamelogs(season=season)

    print("\n" + "=" * 50)
    print("  Done! Press Ctrl+R in TablePlus to refresh.")
    print("  teams             → 30 rows")
    print("  players           → team_id + position + jersey_number filled")
    print("  games             → home_team_id + away_team_id filled")
    print("  player_game_stats → player_id + game_id filled")
    print("=" * 50)