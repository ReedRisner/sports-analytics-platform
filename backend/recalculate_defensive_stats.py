# backend/fix_defensive_stats.py
"""
Fixed version of fetch_defensive_stats_by_position that properly handles OPP_TEAM_ID
Run: python fix_defensive_stats.py
"""

import pandas as pd
from datetime import date, timedelta
from app.database import SessionLocal
from app.models.player import Player, Team
from app.services.nba_fetcher import nba_get, parse_rs, safe_float

MIN_DEF_MINUTES = 15.0
GAMELOGS_URL = "https://stats.nba.com/stats/playergamelogs"

# Position bucket mapping
POS_BUCKET = {
    'G':   'G',
    'G-F': 'GF',
    'F-G': 'GF',
    'F':   'F',
    'F-C': 'FC',
    'C-F': 'FC',
    'C':   'C',
}

BUCKET_COL = {
    'G':  'g',
    'GF': 'gf',
    'F':  'f',
    'FC': 'fc',
    'C':  'c',
}

STAT_COLS = ['pts', 'ast', 'reb', 'stl', 'blk', 'three_pointers_made']

def _normalize(name: str) -> str:
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.lower().strip()

print("="*60)
print("Fetching and calculating defensive stats with 3PM...")
print("="*60)

db = SessionLocal()

try:
    season = "2025-26"
    
    print(f"\n1. Fetching player gamelogs for {season}...")
    data = nba_get(GAMELOGS_URL, {
        "Season": season, 
        "SeasonType": "Regular Season", 
        "LeagueID": "00"
    })
    col_names, rows = parse_rs(data, 0)
    df = pd.DataFrame(rows, columns=col_names)
    print(f"   ✅ {len(df)} player-game rows")

    # Filter by minutes
    df['MIN'] = pd.to_numeric(df['MIN'], errors='coerce').fillna(0)
    df = df[df['MIN'] >= MIN_DEF_MINUTES].copy()
    print(f"   ✅ {len(df)} rows after MIN >= {MIN_DEF_MINUTES} filter")

    # Build lookups
    print("\n2. Building team and player lookups...")
    players_q = db.query(Player.id, Player.position).filter(Player.position != None).all()
    pos_lookup = {p.id: p.position for p in players_q}
    
    teams_q = db.query(Team).all()
    abbrev_map = {t.abbreviation: t.id for t in teams_q if t.abbreviation}
    
    # Also create normalized name mapping for better matching
    name_map = {_normalize(t.name): t.id for t in teams_q}
    print(f"   ✅ {len(pos_lookup)} players, {len(abbrev_map)} teams")

    # Map player positions
    print("\n3. Mapping player positions...")
    df['PLAYER_ID'] = df['PLAYER_ID'].astype(int)
    df['RAW_POS'] = df['PLAYER_ID'].map(pos_lookup)
    df = df[df['RAW_POS'].notna()].copy()
    df['POS_BUCKET'] = df['RAW_POS'].map(POS_BUCKET)
    df = df[df['POS_BUCKET'].notna()].copy()
    print(f"   ✅ {len(df)} rows with valid positions")

    # Determine opponent team from MATCHUP
    print("\n4. Determining opponent teams...")
    def get_opp_id(matchup):
        """Extract opponent team ID from MATCHUP string like 'LAL vs. GSW' or 'LAL @ GSW'"""
        if pd.isna(matchup):
            return None
            
        matchup_str = str(matchup).strip()
        
        # Split by @ or vs.
        if ' @ ' in matchup_str:
            parts = matchup_str.split(' @ ')
            opp_abbr = parts[1].strip() if len(parts) > 1 else ''
        elif ' vs. ' in matchup_str:
            parts = matchup_str.split(' vs. ')
            opp_abbr = parts[1].strip() if len(parts) > 1 else ''
        else:
            # Try to parse manually
            parts = matchup_str.replace('vs.', ' ').replace('@', ' ').split()
            opp_abbr = parts[-1].strip() if parts else ''
        
        # Look up in abbrev map
        return abbrev_map.get(opp_abbr)

    df['OPP_TEAM_ID'] = df['MATCHUP'].apply(get_opp_id)
    
    # Remove rows where we couldn't determine opponent
    before_count = len(df)
    df = df[df['OPP_TEAM_ID'].notna()].copy()
    after_count = len(df)
    print(f"   ✅ {after_count} rows with valid opponent ({before_count - after_count} dropped)")

    # Convert stat columns to numeric
    print("\n5. Converting stats to numeric...")
    for col in ['PTS', 'AST', 'REB', 'STL', 'BLK', 'FG3M']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    print(f"   ✅ Stats converted")

    # Calculate averages by team and position
    print("\n6. Calculating defensive averages by team and position...")
    grouped = df.groupby(['OPP_TEAM_ID', 'POS_BUCKET'])[
        ['PTS', 'AST', 'REB', 'STL', 'BLK', 'FG3M']
    ].mean().reset_index()
    print(f"   ✅ {len(grouped)} team-position combinations")

    # Build team_avgs dict
    team_avgs = {}
    for _, row in grouped.iterrows():
        tid = row['OPP_TEAM_ID']
        bucket = row['POS_BUCKET']
        
        if tid not in team_avgs:
            team_avgs[tid] = {}
        
        team_avgs[tid][bucket] = {
            'pts': safe_float(row['PTS']),
            'ast': safe_float(row['AST']),
            'reb': safe_float(row['REB']),
            'stl': safe_float(row['STL']),
            'blk': safe_float(row['BLK']),
            'three_pointers_made': safe_float(row['FG3M']),
        }

    # Write to database
    print("\n7. Saving defensive averages to database...")
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
    print(f"   ✅ {updated} values saved across {len(team_avgs)} teams")

    # Calculate ranks
    print("\n8. Calculating defensive ranks...")
    all_teams = db.query(Team).all()
    
    for stat in STAT_COLS:
        for bucket, col_suffix in BUCKET_COL.items():
            avg_col = f"{stat}_allowed_{col_suffix}"
            rank_col = f"{stat}_rank_{col_suffix}"
            
            # Collect (team, value) pairs
            vals = []
            for team in all_teams:
                v = getattr(team, avg_col, None)
                if v is not None:
                    vals.append((team, v))
            
            if not vals:
                continue
            
            # Sort descending (most allowed = rank 1 = easiest matchup)
            vals.sort(key=lambda x: x[1], reverse=True)
            for rank_num, (team, _) in enumerate(vals, start=1):
                if hasattr(team, rank_col):
                    setattr(team, rank_col, rank_num)
    
    db.commit()
    print(f"   ✅ Ranks calculated")

    # Verification
    print("\n9. Verification - 3PM allowed to Guards:")
    sample = db.query(Team).filter(Team.three_pointers_made_allowed_g != None).all()
    sample_sorted = sorted(sample, key=lambda t: t.three_pointers_made_allowed_g or 0, reverse=True)
    
    for t in sample_sorted[:5]:
        rank = t.three_pointers_made_rank_g or '?'
        avg = t.three_pointers_made_allowed_g or 0
        print(f"   #{rank:>2}  {t.name:<30} {avg:.2f} 3PM/game")
    
    print("\n" + "="*60)
    print("✅ SUCCESS! Defensive stats including 3PM have been updated.")
    print("Restart backend: uvicorn app.main:app --reload")
    print("="*60)

except Exception as e:
    db.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()