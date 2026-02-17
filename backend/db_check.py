# Run with: python db_check.py
from app.database import SessionLocal
from app.models.player import Team, Player, PlayerGameStats, Game
from sqlalchemy import desc

db = SessionLocal()

print("=" * 50)
print("  DATABASE HEALTH CHECK")
print("=" * 50)

# ── Row counts ────────────────────────────────────
print("\n ROW COUNTS")
print(f"  Teams:       {db.query(Team).count()}  (expected: 30)")
print(f"  Players:     {db.query(Player).count()}  (expected: 500+)")
print(f"  Games:       {db.query(Game).count()}  (expected: 1000+)")
print(f"  Stat lines:  {db.query(PlayerGameStats).count()}  (expected: 20000+)")

# ── Players null check ────────────────────────────
print("\n PLAYERS — NULL CHECK")
print(f"  Missing team_id:       {db.query(Player).filter(Player.team_id == None).count()}")
print(f"  Missing position:      {db.query(Player).filter(Player.position == None).count()}")
print(f"  Missing jersey_number: {db.query(Player).filter(Player.jersey_number == None).count()}")

# ── Games null check ──────────────────────────────
print("\n GAMES — NULL CHECK")
print(f"  Missing home_team_id:  {db.query(Game).filter(Game.home_team_id == None).count()}")
print(f"  Missing away_team_id:  {db.query(Game).filter(Game.away_team_id == None).count()}")
print(f"  Missing date:          {db.query(Game).filter(Game.date == None).count()}")

# ── Stats null check ──────────────────────────────
print("\n PLAYER_GAME_STATS — NULL CHECK")
print(f"  Missing player_id:  {db.query(PlayerGameStats).filter(PlayerGameStats.player_id == None).count()}")
print(f"  Missing game_id:    {db.query(PlayerGameStats).filter(PlayerGameStats.game_id == None).count()}")
print(f"  Missing points:     {db.query(PlayerGameStats).filter(PlayerGameStats.points == None).count()}")

# ── Top 5 PRA games ───────────────────────────────
print("\n SAMPLE — TOP 5 PRA GAMES")
top = (
    db.query(PlayerGameStats, Player)
    .join(Player, PlayerGameStats.player_id == Player.id)
    .order_by(desc(PlayerGameStats.pra))
    .limit(5)
    .all()
)
for stat, player in top:
    print(f"  {player.name:<25} PRA:{stat.pra}  PTS:{stat.points}  REB:{stat.rebounds}  AST:{stat.assists}")

# ── Sample players with full details ─────────────
print("\n SAMPLE — 5 PLAYERS WITH FULL DETAILS")
players = (
    db.query(Player)
    .filter(Player.team_id != None, Player.position != None, Player.jersey_number != None)
    .limit(5)
    .all()
)
for p in players:
    team = db.query(Team).filter(Team.id == p.team_id).first()
    print(f"  {p.name:<25} #{str(p.jersey_number):<3} {str(p.position):<5} {team.name if team else '?'}")

# ── Sample games with both teams ──────────────────
print("\n SAMPLE — 5 GAMES WITH BOTH TEAMS")
games = (
    db.query(Game)
    .filter(Game.home_team_id != None, Game.away_team_id != None)
    .limit(5)
    .all()
)
for g in games:
    home = db.query(Team).filter(Team.id == g.home_team_id).first()
    away = db.query(Team).filter(Team.id == g.away_team_id).first()
    print(f"  {str(g.date):<12} {away.abbreviation if away else '?'} @ {home.abbreviation if home else '?'}")

print("\n" + "=" * 50)
db.close()
