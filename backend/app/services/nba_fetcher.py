# backend/app/services/nba_fetcher.py
import time
import requests
import pandas as pd
from nba_api.stats.static import teams as nba_teams_static
from nba_api.stats.endpoints import leaguedashteamstats
from app.database import SessionLocal
from app.models.player import Team, Player, PlayerGameStats, Game

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://www.nba.com/',
})

GAMELOGS_URL     = "https://stats.nba.com/stats/playergamelogs"
TEAMGAMELOGS_URL = "https://stats.nba.com/stats/teamgamelogs"
ROSTER_URL       = "https://stats.nba.com/stats/commonteamroster"
STANDINGS_URL    = "https://stats.nba.com/stats/leaguestandingsv3"
FALLBACK         = "2024-25"


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
    resp = SESSION.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def parse_rs(data, index=0):
    rs = data['resultSets'][index]
    return rs['headers'], rs['rowSet']

def rval(headers, row, col, default=0):
    try:
        idx = headers.index(col)
        v   = row[idx]
        return v if v is not None else default
    except (ValueError, IndexError):
        return default

def get_team_stats_df(season, measure_type, per_mode="PerGame"):
    kwargs = dict(
        measure_type_detailed_defense = measure_type,
        per_mode_detailed             = per_mode,
        season                        = season,
        season_type_all_star          = "Regular Season",
        last_n_games                  = 0,
        month                         = 0,
        opponent_team_id              = 0,
        pace_adjust                   = "N",
        period                        = 0,
        plus_minus                    = "N",
        rank                          = "N",
        date_from_nullable            = "",
        date_to_nullable              = "",
        game_segment_nullable         = "",
        location_nullable             = "",
        outcome_nullable              = "",
        season_segment_nullable       = "",
        vs_conference_nullable        = "",
        vs_division_nullable          = "",
    )
    try:
        df = leaguedashteamstats.LeagueDashTeamStats(**kwargs).get_data_frames()[0]
        print(f"    ✓ {measure_type} ({season}): {len(df)} teams")
        return df
    except Exception as e:
        print(f"    {season} failed ({e}) → fallback {FALLBACK}")
        kwargs['season'] = FALLBACK
        df = leaguedashteamstats.LeagueDashTeamStats(**kwargs).get_data_frames()[0]
        print(f"    ✓ {measure_type} ({FALLBACK}): {len(df)} teams")
        return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Seed 30 teams
# ─────────────────────────────────────────────────────────────────────────────
def seed_teams():
    db = SessionLocal()
    try:
        teams = nba_teams_static.get_teams()
        added = 0
        for t in teams:
            if not db.query(Team).filter(Team.id == t['id']).first():
                db.add(Team(id=t['id'], name=t['full_name'], abbreviation=t['abbreviation']))
                added += 1
        db.commit()
        print(f"  ✓ {added} teams added ({len(teams)} total)")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Team stats: pace, off/def rating, PPG, opp PPG
# ─────────────────────────────────────────────────────────────────────────────
def fetch_team_stats(season="2025-26"):
    db = SessionLocal()
    try:
        print("  Fetching PPG (Base)...")
        df_base = get_team_stats_df(season, "Base")
        ppg_map = dict(zip(df_base['TEAM_ID'].astype(int), df_base['PTS'].astype(float)))
        time.sleep(1)

        print("  Fetching opp PPG (Opponent)...")
        df_opp  = get_team_stats_df(season, "Opponent")
        opp_col = 'OPP_PTS' if 'OPP_PTS' in df_opp.columns else 'PTS'
        opp_map = dict(zip(df_opp['TEAM_ID'].astype(int), df_opp[opp_col].astype(float)))
        time.sleep(1)

        print("  Fetching pace + ratings (Advanced)...")
        df_adv  = get_team_stats_df(season, "Advanced")
        time.sleep(1)

        updated = 0
        for _, row in df_adv.iterrows():
            tid  = int(row['TEAM_ID'])
            team = db.query(Team).filter(Team.id == tid).first()
            if not team:
                continue
            team.pace             = safe_float(row.get('PACE') or row.get('PACE_PER40') or 0)
            team.offensive_rating = safe_float(row.get('OFF_RATING') or row.get('E_OFF_RATING') or 0)
            team.defensive_rating = safe_float(row.get('DEF_RATING') or row.get('E_DEF_RATING') or 0)
            team.points_per_game     = ppg_map.get(tid)
            team.opp_points_per_game = opp_map.get(tid)
            updated += 1

        db.commit()
        print(f"  ✓ Team stats saved for {updated} teams")
        sample = db.query(Team).filter(Team.pace != None).first()
        if sample:
            print(f"  Sample: {sample.name} → pace={sample.pace}, offRtg={sample.offensive_rating}, defRtg={sample.defensive_rating}, PPG={sample.points_per_game}, oppPPG={sample.opp_points_per_game}")
        time.sleep(1)

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Standings: overall W/L only
# ─────────────────────────────────────────────────────────────────────────────
def fetch_standings(season="2025-26"):
    db = SessionLocal()
    try:
        print("  Fetching standings...")
        try:
            data = nba_get(STANDINGS_URL, {"Season": season, "SeasonType": "Regular Season", "LeagueID": "00"})
        except Exception:
            print(f"  Falling back to {FALLBACK}...")
            data = nba_get(STANDINGS_URL, {"Season": FALLBACK, "SeasonType": "Regular Season", "LeagueID": "00"})

        headers, rows = parse_rs(data, 0)
        updated = 0
        for row in rows:
            tid  = safe_int(rval(headers, row, 'TeamID'))
            team = db.query(Team).filter(Team.id == tid).first()
            if not team:
                continue
            team.wins   = safe_int(rval(headers, row, 'WINS',   0))
            team.losses = safe_int(rval(headers, row, 'LOSSES', 0))
            updated += 1

        db.commit()
        print(f"  ✓ W/L records saved for {updated} teams")
        time.sleep(1)

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Players with position + jersey from rosters
# ─────────────────────────────────────────────────────────────────────────────
def seed_players_with_details(season="2025-26"):
    db = SessionLocal()
    try:
        teams   = nba_teams_static.get_teams()
        added   = 0
        updated = 0
        for i, t in enumerate(teams):
            try:
                data    = nba_get(ROSTER_URL, {"TeamID": t['id'], "Season": season})
                headers, rows = parse_rs(data, 0)
                for row in rows:
                    nba_id   = safe_int(rval(headers, row, 'PLAYER_ID'))
                    name     = str(rval(headers, row, 'PLAYER', ''))
                    position = str(rval(headers, row, 'POSITION', ''))
                    jersey   = str(rval(headers, row, 'NUM', ''))
                    if not nba_id:
                        continue
                    player = db.query(Player).filter(Player.id == nba_id).first()
                    if not player:
                        db.add(Player(
                            id=nba_id, name=name, team_id=t['id'],
                            position=position[:5] if position else None,
                            jersey_number=safe_int(jersey) if jersey.isdigit() else None,
                            is_active=True
                        ))
                        added += 1
                    else:
                        player.team_id       = t['id']
                        player.position      = position[:5] if position else player.position
                        player.jersey_number = safe_int(jersey) if jersey.isdigit() else player.jersey_number
                        updated += 1
                db.commit()
                print(f"  [{i+1}/30] {t['full_name']}")
                time.sleep(0.6)
            except Exception as e:
                print(f"  [{i+1}/30] {t['full_name']} — skipped ({e})")
                time.sleep(1)
        print(f"  ✓ {added} added, {updated} updated")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Points allowed by position
# Runs AFTER step 4 so player positions exist in DB
# ─────────────────────────────────────────────────────────────────────────────
def fetch_pts_allowed_by_position(season="2025-26"):
    db = SessionLocal()
    try:
        print(f"  Fetching player gamelogs for position grouping...")
        data = nba_get(GAMELOGS_URL, {
            "Season": season, "SeasonType": "Regular Season", "LeagueID": "00"
        })
        col_names, rows = parse_rs(data, 0)
        df = pd.DataFrame(rows, columns=col_names)
        print(f"  ✓ {len(df)} player-game rows")

        players_q  = db.query(Player.id, Player.position).filter(Player.position != None).all()
        pos_lookup = {p.id: p.position for p in players_q}
        abbrev_map = {t.abbreviation: t.id for t in db.query(Team).all() if t.abbreviation}

        df['POSITION']    = df['PLAYER_ID'].astype(int).map(pos_lookup)
        df                = df[df['POSITION'].notna()].copy()

        def get_opp_id(matchup):
            parts    = str(matchup).replace('vs.', '@').split('@')
            opp_abbr = parts[1].strip() if len(parts) > 1 else ''
            return abbrev_map.get(opp_abbr)

        df['OPP_TEAM_ID'] = df['MATCHUP'].apply(get_opp_id)
        df                = df[df['OPP_TEAM_ID'].notna()].copy()
        df['PTS']         = pd.to_numeric(df['PTS'], errors='coerce').fillna(0)

        grouped = df.groupby(['OPP_TEAM_ID', 'POSITION'])['PTS'].mean().reset_index()
        grouped.columns = ['OPP_TEAM_ID', 'POSITION', 'AVG_PTS']

        pos_col_map = {
            'G':   'pts_allowed_pg',
            'F':   'pts_allowed_sf',
            'C':   'pts_allowed_c',
            'G-F': 'pts_allowed_sg',
            'F-G': 'pts_allowed_sg',
            'F-C': 'pts_allowed_pf',
            'C-F': 'pts_allowed_pf',
        }

        updated = 0
        for _, row in grouped.iterrows():
            opp_tid  = row['OPP_TEAM_ID']
            position = str(row['POSITION']).strip()
            avg_pts  = safe_float(row['AVG_PTS'])
            col_name = pos_col_map.get(position)
            if not col_name:
                continue
            team = db.query(Team).filter(Team.id == opp_tid).first()
            if team:
                setattr(team, col_name, avg_pts)
                updated += 1

        db.commit()
        print(f"  ✓ Points allowed by position saved ({updated} entries)")
        sample = db.query(Team).filter(Team.pts_allowed_pg != None).first()
        if sample:
            print(f"  Sample: {sample.name} → G:{sample.pts_allowed_pg:.1f}  F:{sample.pts_allowed_sf:.1f}  C:{sample.pts_allowed_c:.1f}")
        time.sleep(1)

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Real game scores + player stat lines
# ─────────────────────────────────────────────────────────────────────────────
def fetch_player_gamelogs(season="2025-26"):
    db = SessionLocal()
    try:
        # Real scores from teamgamelogs
        print(f"  Fetching real team scores (teamgamelogs)...")
        score_data       = nba_get(TEAMGAMELOGS_URL, {"Season": season, "SeasonType": "Regular Season", "LeagueID": "00"})
        score_cols, score_rows = parse_rs(score_data, 0)
        df_scores        = pd.DataFrame(score_rows, columns=score_cols)
        df_scores['PTS'] = pd.to_numeric(df_scores['PTS'], errors='coerce').fillna(0).astype(int)
        df_scores['TEAM_ID'] = df_scores['TEAM_ID'].astype(int)

        home_sc = df_scores[df_scores['MATCHUP'].str.contains('vs\\.', na=False)][
            ['GAME_ID','GAME_DATE','TEAM_ID','PTS']
        ].rename(columns={'TEAM_ID':'HOME_TEAM_ID','PTS':'HOME_PTS'})

        away_sc = df_scores[df_scores['MATCHUP'].str.contains(' @ ', na=False)][
            ['GAME_ID','TEAM_ID','PTS']
        ].rename(columns={'TEAM_ID':'AWAY_TEAM_ID','PTS':'AWAY_PTS'})

        games_df = pd.merge(
            home_sc[['GAME_ID','GAME_DATE','HOME_TEAM_ID','HOME_PTS']],
            away_sc[['GAME_ID','AWAY_TEAM_ID','AWAY_PTS']],
            on='GAME_ID'
        )
        print(f"  ✓ {len(games_df)} unique games")
        for _, r in games_df.head(3).iterrows():
            print(f"    {r['GAME_ID']}: HOME {r['HOME_PTS']} vs AWAY {r['AWAY_PTS']}")

        game_cache = {}
        for _, grow in games_df.iterrows():
            nba_game_id = str(grow['GAME_ID'])
            game = Game(
                nba_game_id  = nba_game_id,
                date         = str(grow['GAME_DATE'])[:10],
                home_team_id = int(grow['HOME_TEAM_ID']),
                away_team_id = int(grow['AWAY_TEAM_ID']),
                home_score   = int(grow['HOME_PTS']),
                away_score   = int(grow['AWAY_PTS']),
                status       = 'final'
            )
            db.add(game)
            db.flush()
            game_cache[nba_game_id] = game.id

        db.commit()
        print(f"  ✓ Saved {len(game_cache)} games with real scores")
        time.sleep(1)

        # Player stat lines
        print(f"  Fetching player game logs...")
        data = nba_get(GAMELOGS_URL, {"Season": season, "SeasonType": "Regular Season", "LeagueID": "00"})
        col_names, rows = parse_rs(data, 0)
        df_all = pd.DataFrame(rows, columns=col_names)
        print(f"  ✓ {len(df_all)} player-game rows")

        team_cache = {}
        saved      = 0

        for _, row in df_all.iterrows():
            player_name   = row.get('PLAYER_NAME', '')
            nba_player_id = safe_int(row.get('PLAYER_ID'))
            nba_team_id   = safe_int(row.get('TEAM_ID'))
            nba_game_id   = str(row.get('GAME_ID', ''))

            if not player_name or nba_game_id not in game_cache:
                continue

            if nba_team_id not in team_cache:
                team_cache[nba_team_id] = db.query(Team).filter(Team.id == nba_team_id).first()
            team = team_cache[nba_team_id]

            player = db.query(Player).filter(Player.id == nba_player_id).first()
            if not player:
                player = Player(id=nba_player_id, name=player_name, is_active=True)
                db.add(player)
                db.flush()
            if team and player.team_id != team.id:
                player.team_id = team.id

            points     = safe_int(row.get('PTS'))
            rebounds   = safe_int(row.get('REB'))
            assists    = safe_int(row.get('AST'))
            oreb       = safe_int(row.get('OREB'))
            dreb       = safe_int(row.get('DREB'))
            fgm        = safe_int(row.get('FGM'))
            fga        = safe_int(row.get('FGA'))
            fg_pct     = safe_float(row.get('FG_PCT'))
            fg3m       = safe_int(row.get('FG3M'))
            fg3a       = safe_int(row.get('FG3A'))
            fg3_pct    = safe_float(row.get('FG3_PCT'))
            ftm        = safe_int(row.get('FTM'))
            fta        = safe_int(row.get('FTA'))
            ft_pct     = safe_float(row.get('FT_PCT'))
            steals     = safe_int(row.get('STL'))
            blocks     = safe_int(row.get('BLK'))
            turnovers  = safe_int(row.get('TOV'))
            plus_minus = safe_int(row.get('PLUS_MINUS'))
            minutes    = safe_float(row.get('MIN'))

            db.add(PlayerGameStats(
                player_id      = player.id,
                game_id        = game_cache[nba_game_id],
                minutes        = minutes,
                points         = points,
                rebounds       = rebounds,
                assists        = assists,
                oreb           = oreb,
                dreb           = dreb,
                fgm            = fgm,
                fga            = fga,
                fg_pct         = fg_pct,
                fg3m           = fg3m,
                fg3a           = fg3a,
                fg3_pct        = fg3_pct,
                ftm            = ftm,
                fta            = fta,
                ft_pct         = ft_pct,
                steals         = steals,
                blocks         = blocks,
                turnovers      = turnovers,
                plus_minus     = plus_minus,
                pra            = points + rebounds + assists,
                pr             = points + rebounds,
                pa             = points + assists,
                ra             = rebounds + assists,
                fantasy_points = safe_float(row.get('NBA_FANTASY_PTS')),
            ))
            saved += 1

            if saved % 500 == 0:
                db.commit()
                print(f"  Saved {saved} / {len(df_all)} stat lines...")

        db.commit()
        print(f"  ✓ Saved {saved} player stat lines")

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    season = sys.argv[1] if len(sys.argv) > 1 else "2025-26"

    print("=" * 55)
    print(f"  NBA Data Fetcher — {season}")
    print("=" * 55)

    print("\n[1/6] Seeding teams...")
    seed_teams()

    print(f"\n[2/6] Team stats: pace, ratings, PPG, opp PPG...")
    fetch_team_stats(season=season)

    print(f"\n[3/6] Standings: W/L records...")
    fetch_standings(season=season)

    print(f"\n[4/6] Players: position + jersey from rosters...")
    seed_players_with_details(season=season)

    print(f"\n[5/6] Points allowed by position...")
    fetch_pts_allowed_by_position(season=season)

    print(f"\n[6/6] Game logs + real scores...")
    fetch_player_gamelogs(season=season)

    print("\n" + "=" * 55)
    print("  Done! Run python db_check.py to verify.")
    print("=" * 55)