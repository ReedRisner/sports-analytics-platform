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

GAMELOGS_URL          = "https://stats.nba.com/stats/playergamelogs"
GAMELOGS_ADVANCED_URL = "https://stats.nba.com/stats/playergamelogs"
TEAMGAMELOGS_URL      = "https://stats.nba.com/stats/teamgamelogs"
ROSTER_URL            = "https://stats.nba.com/stats/commonteamroster"
STANDINGS_URL         = "https://stats.nba.com/stats/leaguestandingsv3"
FALLBACK              = "2024-25"

# ── Position bucketing ────────────────────────────────────────────────────────
# NBA API raw values → our 5 canonical groups
#   G   = pure guard
#   G-F = guard/forward combo
#   F   = pure forward (also F-G maps here)
#   F-C = forward/center combo (also C-F maps here)
#   C   = pure center
POS_BUCKET = {
    'G':   'G',
    'G-F': 'GF',
    'F-G': 'GF',    # treat same as G-F
    'F':   'F',
    'F-C': 'FC',
    'C-F': 'FC',    # treat same as F-C
    'C':   'C',
}

# Maps bucket → Team column prefix
BUCKET_COL = {
    'G':  'g',
    'GF': 'gf',
    'F':  'f',
    'FC': 'fc',
    'C':  'c',
}

STAT_COLS = ['pts', 'ast', 'reb', 'stl', 'blk']
STAT_DF_COLS = {
    'pts': 'PTS',
    'ast': 'AST',
    'reb': 'REB',
    'stl': 'STL',
    'blk': 'BLK',
}


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
# STEP 5 — Defensive stats allowed by position group (PTS, AST, REB, STL, BLK)
#           + league ranks (1 = most permissive = easiest matchup)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_defensive_stats_by_position(season="2025-26"):
    """
    For each team, compute the average PTS/AST/REB/STL/BLK allowed to opposing
    players grouped by position bucket (G, GF, F, FC, C), then rank all 30
    teams per stat+position combo (rank 1 = most allowed = best matchup).

    Only player-games with MIN >= MIN_DEF_MINUTES are counted so that
    garbage-time appearances don't dilute the averages. This means the
    defensive numbers reflect real, meaningful minutes played against each team.
    """
    MIN_DEF_MINUTES = 15.0   # only count games where opp player played 15+ min

    db = SessionLocal()
    try:
        print(f"  Fetching player gamelogs for defensive position breakdown...")
        data = nba_get(GAMELOGS_URL, {
            "Season": season, "SeasonType": "Regular Season", "LeagueID": "00"
        })
        col_names, rows = parse_rs(data, 0)
        df = pd.DataFrame(rows, columns=col_names)
        print(f"  ✓ {len(df)} player-game rows (before minutes filter)")

        # ── Minutes filter — only meaningful appearances ──────────────────────
        df['MIN'] = pd.to_numeric(df['MIN'], errors='coerce').fillna(0)
        df = df[df['MIN'] >= MIN_DEF_MINUTES].copy()
        print(f"  ✓ {len(df)} rows after MIN >= {MIN_DEF_MINUTES} filter")

        # Build lookups
        players_q  = db.query(Player.id, Player.position).filter(Player.position != None).all()
        pos_lookup = {p.id: p.position for p in players_q}
        abbrev_map = {t.abbreviation: t.id for t in db.query(Team).all() if t.abbreviation}

        # Map raw position → bucket
        df['RAW_POS'] = df['PLAYER_ID'].astype(int).map(pos_lookup)
        df = df[df['RAW_POS'].notna()].copy()
        df['POS_BUCKET'] = df['RAW_POS'].map(POS_BUCKET)
        df = df[df['POS_BUCKET'].notna()].copy()

        # Determine opponent team from MATCHUP string (e.g. "LAL vs. GSW" or "LAL @ GSW")
        def get_opp_id(matchup):
            parts    = str(matchup).replace('vs.', '@').split('@')
            opp_abbr = parts[1].strip() if len(parts) > 1 else ''
            return abbrev_map.get(opp_abbr)

        df['OPP_TEAM_ID'] = df['MATCHUP'].apply(get_opp_id)
        df = df[df['OPP_TEAM_ID'].notna()].copy()

        for col in ['PTS', 'AST', 'REB', 'STL', 'BLK']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # ── Compute per-team, per-bucket averages ───────────────────────────
        grouped = df.groupby(['OPP_TEAM_ID', 'POS_BUCKET'])[['PTS', 'AST', 'REB', 'STL', 'BLK']].mean().reset_index()

        # Build a dict: team_id → {bucket → {stat → avg}}
        team_avgs = {}
        for _, row in grouped.iterrows():
            tid    = row['OPP_TEAM_ID']
            bucket = row['POS_BUCKET']
            if tid not in team_avgs:
                team_avgs[tid] = {}
            team_avgs[tid][bucket] = {
                'pts': safe_float(row['PTS']),
                'ast': safe_float(row['AST']),
                'reb': safe_float(row['REB']),
                'stl': safe_float(row['STL']),
                'blk': safe_float(row['BLK']),
            }

        # Write averages to DB
        updated = 0
        for tid, buckets in team_avgs.items():
            team = db.query(Team).filter(Team.id == tid).first()
            if not team:
                continue
            for bucket, stats in buckets.items():
                col_suffix = BUCKET_COL.get(bucket)
                if not col_suffix:
                    continue
                for stat in STAT_COLS:
                    col_name = f"{stat}_allowed_{col_suffix}"
                    if hasattr(team, col_name):
                        setattr(team, col_name, stats[stat])
                        updated += 1
        db.commit()
        print(f"  ✓ Defensive averages saved ({updated} values across {len(team_avgs)} teams)")

        # ── Compute ranks ────────────────────────────────────────────────────
        # For each stat+bucket combo, rank 30 teams descending (most allowed = rank 1)
        print("  Computing league ranks...")
        all_teams = db.query(Team).all()

        for stat in STAT_COLS:
            for bucket, col_suffix in BUCKET_COL.items():
                avg_col  = f"{stat}_allowed_{col_suffix}"
                rank_col = f"{stat}_rank_{col_suffix}"

                # Collect (team, value) pairs, skip nulls
                vals = []
                for team in all_teams:
                    v = getattr(team, avg_col, None)
                    if v is not None:
                        vals.append((team, v))

                if not vals:
                    continue

                # Sort descending, assign rank 1 to highest (most permissive)
                vals.sort(key=lambda x: x[1], reverse=True)
                for rank_num, (team, _) in enumerate(vals, start=1):
                    if hasattr(team, rank_col):
                        setattr(team, rank_col, rank_num)

        db.commit()
        print("  ✓ Ranks saved")

        # ── Verification sample ──────────────────────────────────────────────
        print("\n  VERIFICATION — PTS allowed to G (sorted by most permissive):")
        sample_teams = db.query(Team).filter(Team.pts_allowed_g != None).all()
        sample_sorted = sorted(sample_teams, key=lambda t: t.pts_allowed_g, reverse=True)
        for t in sample_sorted[:5]:
            print(f"    #{t.pts_rank_g:>2}  {t.name:<30} {t.pts_allowed_g:.2f} pts/game to Gs")
        print("    ...")
        for t in sample_sorted[-3:]:
            print(f"    #{t.pts_rank_g:>2}  {t.name:<30} {t.pts_allowed_g:.2f} pts/game to Gs")

        time.sleep(1)

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Real game scores + player stat lines (with usage_rate)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_player_gamelogs(season="2025-26"):
    db = SessionLocal()
    try:
        # ── Real scores from teamgamelogs ────────────────────────────────────
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

        # ── Base player game logs ────────────────────────────────────────────
        print(f"  Fetching base player game logs...")
        base_data = nba_get(GAMELOGS_URL, {
            "Season": season,
            "SeasonType": "Regular Season",
            "LeagueID": "00",
            "MeasureType": "Base",
        })
        base_cols, base_rows = parse_rs(base_data, 0)
        df_base = pd.DataFrame(base_rows, columns=base_cols)
        print(f"  ✓ {len(df_base)} base stat rows")
        time.sleep(1)

        # ── Advanced player game logs (for USG_PCT) ───────────────────────────
        print(f"  Fetching advanced player game logs (usage rate)...")
        try:
            adv_data = nba_get(GAMELOGS_URL, {
                "Season": season,
                "SeasonType": "Regular Season",
                "LeagueID": "00",
                "MeasureType": "Advanced",
            })
            adv_cols, adv_rows = parse_rs(adv_data, 0)
            df_adv = pd.DataFrame(adv_rows, columns=adv_cols)
            # Build lookup: (PLAYER_ID, GAME_ID) → USG_PCT
            usg_col = 'USG_PCT' if 'USG_PCT' in df_adv.columns else None
            if usg_col:
                df_adv['_key'] = df_adv['PLAYER_ID'].astype(str) + '_' + df_adv['GAME_ID'].astype(str)
                usg_lookup = dict(zip(df_adv['_key'], df_adv[usg_col]))
                print(f"  ✓ {len(usg_lookup)} usage rate entries")
            else:
                usg_lookup = {}
                print("  ⚠ USG_PCT not found in advanced logs — will store NULL")
        except Exception as e:
            usg_lookup = {}
            print(f"  ⚠ Advanced logs failed ({e}) — usage_rate will be NULL")
        time.sleep(1)

        # ── Save player stat lines ────────────────────────────────────────────
        team_cache = {}
        saved      = 0

        for _, row in df_base.iterrows():
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

            # Look up usage from advanced logs
            usg_key    = f"{nba_player_id}_{nba_game_id}"
            usage_rate = safe_float(usg_lookup.get(usg_key)) if usg_lookup.get(usg_key) is not None else None

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
                usage_rate     = usage_rate,
                pra            = points + rebounds + assists,
                pr             = points + rebounds,
                pa             = points + assists,
                ra             = rebounds + assists,
                fantasy_points = safe_float(row.get('NBA_FANTASY_PTS')),
            ))
            saved += 1

            if saved % 500 == 0:
                db.commit()
                print(f"  Saved {saved} / {len(df_base)} stat lines...")

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
# STEP 7 — Full season schedule (past + future games)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_schedule(season="2025-26"):
    """
    Pull the complete NBA regular season schedule via scheduleleaguev2.

    Response structure:
      leagueSchedule.gameDates[].games[]
        gameId, gameStatus, gameStatusText, gameDate*
        homeTeam.teamId, awayTeam.teamId

    Completed games already exist from fetch_player_gamelogs and are skipped
    by nba_game_id. Future games are inserted with status='scheduled' so the
    odds fetcher can match them by date + team.
    """
    from datetime import date as date_type

    db = SessionLocal()
    try:
        print(f"  Fetching full season schedule ({season})...")
        data = nba_get(
            "https://stats.nba.com/stats/scheduleleaguev2",
            {"LeagueID": "00", "Season": season},
        )

        league_schedule = data.get("leagueSchedule", {})
        game_dates      = league_schedule.get("gameDates", [])
        print(f"  ✓ {len(game_dates)} game dates in schedule")

        # Build set of already-stored nba_game_ids to avoid duplicates
        existing_ids = {g.nba_game_id for g in db.query(Game.nba_game_id).all()}

        # Build set of valid team IDs so we skip preseason/international games
        # that have fake team IDs (e.g. 15016, 50013) not in our teams table
        valid_team_ids = {t.id for t in db.query(Team).all()}

        added   = 0
        skipped = 0

        for game_date_entry in game_dates:
            # gameDate format: "10/02/2025 00:00:00" → convert to YYYY-MM-DD
            raw_date = game_date_entry.get("gameDate", "")
            try:
                from datetime import datetime
                game_date = datetime.strptime(raw_date[:10], "%m/%d/%Y").strftime("%Y-%m-%d")
            except Exception:
                game_date = raw_date[:10]

            for game in game_date_entry.get("games", []):
                nba_game_id  = str(game.get("gameId", ""))
                home_team_id = safe_int(game.get("homeTeam", {}).get("teamId"))
                away_team_id = safe_int(game.get("awayTeam", {}).get("teamId"))

                if not nba_game_id or not home_team_id or not away_team_id:
                    continue

                # Skip preseason/international games with non-NBA team IDs
                if home_team_id not in valid_team_ids or away_team_id not in valid_team_ids:
                    continue

                if nba_game_id in existing_ids:
                    skipped += 1
                    continue

                status_text = str(game.get("gameStatusText", "")).strip()
                status      = "final" if "Final" in status_text else "scheduled"

                db.add(Game(
                    nba_game_id  = nba_game_id,
                    date         = game_date,
                    home_team_id = home_team_id,
                    away_team_id = away_team_id,
                    home_score   = None,
                    away_score   = None,
                    status       = status,
                ))
                added += 1

                if added % 200 == 0:
                    db.commit()
                    print(f"  Inserted {added} schedule games...")

        db.commit()
        print(f"  ✓ Schedule: {added} new games inserted, {skipped} already existed")

        upcoming = db.query(Game).filter(
            Game.date   >= date_type.today(),
            Game.status == "scheduled",
        ).count()
        print(f"  ✓ Upcoming scheduled games in DB: {upcoming}")
        time.sleep(1)

    except Exception as e:
        db.rollback()
        print(f"  ✗ Error fetching schedule: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# NIGHTLY UPDATE — incremental refresh (run at 3am PST after games finish)
# ─────────────────────────────────────────────────────────────────────────────
def nightly_update(season="2025-26"):
    """
    Lightweight nightly refresh — only pulls NEW data since the last update.
    Safe to run every night without wiping anything.

    Steps:
      1. Pull new game scores (skips games already in DB by nba_game_id)
      2. Pull new player stat lines (skips existing player_game_stats)
      3. Update standings (W/L records)
      4. Update team stats (pace, ratings, PPG)
      5. Update defensive stats by position + ranks

    Does NOT re-fetch: rosters, full schedule, or historical data.
    Run time: ~2-3 minutes.
    """
    import logging
    log = logging.getLogger(__name__)
    log.info("Nightly NBA update starting...")
    print("=" * 50)
    print(f"  Nightly NBA Update — {season}")
    print("=" * 50)

    db = SessionLocal()
    try:
        # ── Step 1: New game scores ───────────────────────────────────────────
        print("\n[1/5] Fetching new game scores...")
        score_data = nba_get(TEAMGAMELOGS_URL, {
            "Season": season, "SeasonType": "Regular Season", "LeagueID": "00"
        })
        score_cols, score_rows = parse_rs(score_data, 0)
        df_scores = pd.DataFrame(score_rows, columns=score_cols)
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

        # Only process games not already in DB
        existing_game_ids = {g.nba_game_id for g in db.query(Game.nba_game_id).all()}
        game_cache = {}
        new_games = 0

        for _, grow in games_df.iterrows():
            nba_game_id = str(grow['GAME_ID'])

            if nba_game_id in existing_game_ids:
                # Game exists — update scores if it was previously scheduled
                existing = db.query(Game).filter(Game.nba_game_id == nba_game_id).first()
                if existing and existing.home_score is None:
                    existing.home_score = int(grow['HOME_PTS'])
                    existing.away_score = int(grow['AWAY_PTS'])
                    existing.status    = 'final'
                    game_cache[nba_game_id] = existing.id
                else:
                    game_cache[nba_game_id] = existing.id if existing else None
                continue

            # New game — insert it
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
            new_games += 1

        db.commit()
        print(f"  ✓ {new_games} new games added, scores updated for previously scheduled games")
        time.sleep(1)

        # ── Step 2: New player stat lines ─────────────────────────────────────
        print("\n[2/5] Fetching new player stat lines...")

        # Build set of (player_id, game_id) already in DB to skip
        existing_stats = {
            (s.player_id, s.game_id)
            for s in db.query(PlayerGameStats.player_id, PlayerGameStats.game_id).all()
        }

        base_data = nba_get(GAMELOGS_URL, {
            "Season": season, "SeasonType": "Regular Season",
            "LeagueID": "00", "MeasureType": "Base",
        })
        base_cols, base_rows = parse_rs(base_data, 0)
        df_base = pd.DataFrame(base_rows, columns=base_cols)
        time.sleep(1)

        # Advanced logs for usage rate
        try:
            adv_data = nba_get(GAMELOGS_URL, {
                "Season": season, "SeasonType": "Regular Season",
                "LeagueID": "00", "MeasureType": "Advanced",
            })
            adv_cols, adv_rows = parse_rs(adv_data, 0)
            df_adv = pd.DataFrame(adv_rows, columns=adv_cols)
            usg_col = 'USG_PCT' if 'USG_PCT' in df_adv.columns else None
            if usg_col:
                df_adv['_key'] = df_adv['PLAYER_ID'].astype(str) + '_' + df_adv['GAME_ID'].astype(str)
                usg_lookup = dict(zip(df_adv['_key'], df_adv[usg_col]))
            else:
                usg_lookup = {}
        except Exception:
            usg_lookup = {}
        time.sleep(1)

        team_cache = {}
        saved = 0

        for _, row in df_base.iterrows():
            nba_player_id = safe_int(row.get('PLAYER_ID'))
            nba_game_id   = str(row.get('GAME_ID', ''))
            player_name   = row.get('PLAYER_NAME', '')

            if not player_name or nba_game_id not in game_cache:
                continue

            db_game_id = game_cache[nba_game_id]
            if not db_game_id:
                continue

            # Skip if stat line already exists
            if (nba_player_id, db_game_id) in existing_stats:
                continue

            nba_team_id = safe_int(row.get('TEAM_ID'))
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

            points    = safe_int(row.get('PTS'))
            rebounds  = safe_int(row.get('REB'))
            assists   = safe_int(row.get('AST'))
            usg_key   = f"{nba_player_id}_{nba_game_id}"
            usage_rate = safe_float(usg_lookup.get(usg_key)) if usg_lookup.get(usg_key) is not None else None

            db.add(PlayerGameStats(
                player_id   = player.id,
                game_id     = db_game_id,
                minutes     = safe_float(row.get('MIN')),
                points      = points,
                rebounds    = rebounds,
                assists     = assists,
                oreb        = safe_int(row.get('OREB')),
                dreb        = safe_int(row.get('DREB')),
                fgm         = safe_int(row.get('FGM')),
                fga         = safe_int(row.get('FGA')),
                fg_pct      = safe_float(row.get('FG_PCT')),
                fg3m        = safe_int(row.get('FG3M')),
                fg3a        = safe_int(row.get('FG3A')),
                fg3_pct     = safe_float(row.get('FG3_PCT')),
                ftm         = safe_int(row.get('FTM')),
                fta         = safe_int(row.get('FTA')),
                ft_pct      = safe_float(row.get('FT_PCT')),
                steals      = safe_int(row.get('STL')),
                blocks      = safe_int(row.get('BLK')),
                turnovers   = safe_int(row.get('TOV')),
                plus_minus  = safe_int(row.get('PLUS_MINUS')),
                usage_rate  = usage_rate,
                pra         = points + rebounds + assists,
                pr          = points + rebounds,
                pa          = points + assists,
                ra          = rebounds + assists,
                fantasy_points = safe_float(row.get('NBA_FANTASY_PTS')),
            ))
            saved += 1

            if saved % 500 == 0:
                db.commit()
                print(f"  Saved {saved} new stat lines...")

        db.commit()
        print(f"  ✓ {saved} new player stat lines added")
        time.sleep(1)

        # ── Step 3: Standings ─────────────────────────────────────────────────
        print("\n[3/5] Updating standings...")
        fetch_standings(season=season)

        # ── Step 4: Team stats ────────────────────────────────────────────────
        print("\n[4/5] Updating team stats...")
        fetch_team_stats(season=season)

        # ── Step 5: Defensive stats by position ───────────────────────────────
        print("\n[5/5] Updating defensive stats by position...")
        fetch_defensive_stats_by_position(season=season)

        print("\n" + "=" * 50)
        print(f"  ✓ Nightly update complete")
        print(f"    New games: {new_games}")
        print(f"    New stat lines: {saved}")
        print("=" * 50)
        log.info(f"Nightly NBA update complete — {new_games} games, {saved} stat lines")

    except Exception as e:
        db.rollback()
        print(f"  ✗ Nightly update failed: {e}")
        import traceback; traceback.print_exc()
        log.exception(f"Nightly NBA update failed: {e}")
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    season = sys.argv[1] if len(sys.argv) > 1 else "2025-26"

    print("=" * 55)
    print(f"  NBA Data Fetcher — {season}")
    print("=" * 55)

    print("\n[1/7] Seeding teams...")
    seed_teams()

    print(f"\n[2/7] Team stats: pace, ratings, PPG, opp PPG...")
    fetch_team_stats(season=season)

    print(f"\n[3/7] Standings: W/L records...")
    fetch_standings(season=season)

    print(f"\n[4/7] Players: position + jersey from rosters...")
    seed_players_with_details(season=season)

    print(f"\n[5/7] Defensive stats by position (PTS/AST/REB/STL/BLK + ranks)...")
    fetch_defensive_stats_by_position(season=season)

    print(f"\n[6/7] Game logs + real scores + usage rate...")
    fetch_player_gamelogs(season=season)

    print(f"\n[7/7] Full season schedule (future games for odds matching)...")
    fetch_schedule(season=season)

    print("\n" + "=" * 55)
    print("  Done! Run python db_check.py to verify.")
    print("=" * 55)


# ── Quick schedule-only runner ────────────────────────────────────────────────
# Run this to add future games without re-fetching all stats:
#   python -c "from app.services.nba_fetcher import fetch_schedule; fetch_schedule()"