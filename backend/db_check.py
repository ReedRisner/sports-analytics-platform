# backend/db_check.py
from app.database import SessionLocal
from app.models.player import Team, Player, PlayerGameStats, Game
from sqlalchemy import desc

db = SessionLocal()

print("=" * 55)
print("  DATABASE HEALTH CHECK")
print("=" * 55)

# ── Row counts ────────────────────────────────────────────
print("\n ROW COUNTS")
print(f"  Teams:       {db.query(Team).count()}  (expected: 30)")
print(f"  Players:     {db.query(Player).count()}  (expected: 500+)")
print(f"  Games:       {db.query(Game).count()}  (expected: 800+)")
print(f"  Stat lines:  {db.query(PlayerGameStats).count()}  (expected: 17000+)")

# ── Players null check ────────────────────────────────────
print("\n PLAYERS — NULL CHECK")
print(f"  Missing team_id:       {db.query(Player).filter(Player.team_id == None).count()}")
print(f"  Missing position:      {db.query(Player).filter(Player.position == None).count()}")
print(f"  Missing jersey_number: {db.query(Player).filter(Player.jersey_number == None).count()}")

# ── Teams null check ──────────────────────────────────────
print("\n TEAMS — NULL CHECK")
print(f"  Missing pace:             {db.query(Team).filter(Team.pace == None).count()}")
print(f"  Missing offensive_rating: {db.query(Team).filter(Team.offensive_rating == None).count()}")
print(f"  Missing defensive_rating: {db.query(Team).filter(Team.defensive_rating == None).count()}")
print(f"  Missing points_per_game:  {db.query(Team).filter(Team.points_per_game == None).count()}")
print(f"  Missing pts_allowed_pg:   {db.query(Team).filter(Team.pts_allowed_pg == None).count()}")
print(f"  Missing wins:             {db.query(Team).filter(Team.wins == None).count()}")

# ── Games null check ──────────────────────────────────────
print("\n GAMES — NULL CHECK")
print(f"  Missing home_team_id: {db.query(Game).filter(Game.home_team_id == None).count()}")
print(f"  Missing away_team_id: {db.query(Game).filter(Game.away_team_id == None).count()}")
print(f"  Missing home_score:   {db.query(Game).filter(Game.home_score == None).count()}")
print(f"  Missing away_score:   {db.query(Game).filter(Game.away_score == None).count()}")

# ── Stats null check ──────────────────────────────────────
print("\n PLAYER_GAME_STATS — NULL CHECK")
print(f"  Missing player_id:  {db.query(PlayerGameStats).filter(PlayerGameStats.player_id == None).count()}")
print(f"  Missing game_id:    {db.query(PlayerGameStats).filter(PlayerGameStats.game_id == None).count()}")
print(f"  Missing steals:     {db.query(PlayerGameStats).filter(PlayerGameStats.steals == None).count()}")
print(f"  Missing blocks:     {db.query(PlayerGameStats).filter(PlayerGameStats.blocks == None).count()}")
print(f"  Missing ftm:        {db.query(PlayerGameStats).filter(PlayerGameStats.ftm == None).count()}")

# ── Sample team stats ─────────────────────────────────────
print("\n SAMPLE — 5 TEAMS WITH FULL STATS")
teams = db.query(Team).filter(Team.pace != None).limit(5).all()
for t in teams:
    print(f"  {t.name:<30} Pace:{t.pace}  OffRtg:{t.offensive_rating}  DefRtg:{t.defensive_rating}  PPG:{t.points_per_game}  W:{t.wins}-{t.losses}")

# ── Sample pts allowed by position ───────────────────────
print("\n SAMPLE — 3 TEAMS PTS ALLOWED BY POSITION")
teams2 = db.query(Team).filter(Team.pts_allowed_pg != None).limit(3).all()
for t in teams2:
    print(f"  {t.name:<30} PG:{t.pts_allowed_pg}  SG:{t.pts_allowed_sg}  SF:{t.pts_allowed_sf}  PF:{t.pts_allowed_pf}  C:{t.pts_allowed_c}")

# ── Sample game scores ────────────────────────────────────
print("\n SAMPLE — 5 GAMES WITH SCORES")
games = db.query(Game).filter(Game.home_score != None).limit(5).all()
for g in games:
    home = db.query(Team).filter(Team.id == g.home_team_id).first()
    away = db.query(Team).filter(Team.id == g.away_team_id).first()
    print(f"  {str(g.date):<12}  {away.abbreviation if away else '?'} {g.away_score}  @  {home.abbreviation if home else '?'} {g.home_score}")

# ── Top 5 PRA ─────────────────────────────────────────────
print("\n SAMPLE — TOP 5 PRA GAMES")
top = (
    db.query(PlayerGameStats, Player)
    .join(Player, PlayerGameStats.player_id == Player.id)
    .order_by(desc(PlayerGameStats.pra))
    .limit(5)
    .all()
)
for stat, player in top:
    print(f"  {player.name:<25} PRA:{stat.pra}  PTS:{stat.points}  REB:{stat.rebounds}  AST:{stat.assists}  STL:{stat.steals}  BLK:{stat.blocks}")

print("\n" + "=" * 55)
db.close()