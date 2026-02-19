# backend/test_projection_endpoint.py
"""
Test if the projection endpoint works for threes
Run: python test_projection_endpoint.py
"""

from app.database import SessionLocal
from app.services.projection_engine import project_player
from app.models.player import Player

db = SessionLocal()

# Test player ID 1626164 (from the error)
player_id = 1626164
stat_type = 'threes'

print(f"Testing projection for player {player_id}, stat: {stat_type}\n")

# Check if player exists
player = db.query(Player).filter(Player.id == player_id).first()
if player:
    print(f"✅ Player found: {player.name}")
    print(f"   Team: {player.team_id}")
    print(f"   Position: {player.position}")
else:
    print(f"❌ Player {player_id} not found in database!")
    db.close()
    exit(1)

# Check if player has any 3PM stats
from app.models.player import PlayerGameStats
from sqlalchemy import func

stats = db.query(
    func.count(PlayerGameStats.id).label('games'),
    func.avg(PlayerGameStats.three_pointers_made).label('avg_3pm'),
    func.sum(PlayerGameStats.three_pointers_made).label('total_3pm')
).filter(
    PlayerGameStats.player_id == player_id,
    PlayerGameStats.three_pointers_made != None
).first()

print(f"\n3PM Stats for {player.name}:")
print(f"   Games with 3PM data: {stats.games}")
print(f"   Average 3PM: {stats.avg_3pm:.2f}" if stats.avg_3pm else "   Average 3PM: 0.00")
print(f"   Total 3PM: {stats.total_3pm}" if stats.total_3pm else "   Total 3PM: 0")

if stats.games == 0:
    print(f"\n❌ Player has NO 3PM data!")
    print("   This is why projection returns None")
    print("\n   SOLUTION: This player doesn't shoot 3s, or data hasn't been fetched")
    db.close()
    exit(0)

# Try to create projection
print(f"\nAttempting projection...")
try:
    proj = project_player(
        db=db,
        player_id=player_id,
        stat_type=stat_type,
        opp_team_id=None,
        line=None
    )
    
    if proj:
        print(f"✅ Projection succeeded!")
        print(f"   Projected: {proj.projected}")
        print(f"   Season avg: {proj.season_avg}")
        print(f"   L5 avg: {proj.l5_avg}")
        print(f"   L10 avg: {proj.l10_avg}")
    else:
        print(f"⚠️  Projection returned None")
        print(f"   Reasons:")
        print(f"   - Player may have < 3 games with 3PM data")
        print(f"   - Player may not shoot enough 3s")
        
except Exception as e:
    print(f"❌ Projection failed with error:")
    print(f"   {e}")
    import traceback
    traceback.print_exc()

db.close()

print("\n" + "="*60)
print("If projection is None:")
print("1. Player doesn't have enough 3PM data (needs 3+ games)")
print("2. Frontend should handle None gracefully")
print("3. Backend should return 404 or empty response, not undefined")
print("="*60)
