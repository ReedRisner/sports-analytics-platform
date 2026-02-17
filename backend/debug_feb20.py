# backend/debug_odds.py
from app.database import SessionLocal
from app.models.player import Game, OddsLine, Player, Team
from datetime import date, timedelta

db = SessionLocal()

print("Odds lines in DB by date:")
for days in range(5):
    check_date = date.today() + timedelta(days=days)
    games = db.query(Game).filter(Game.date == check_date).all()
    game_ids = [g.id for g in games]
    if game_ids:
        count = db.query(OddsLine).filter(OddsLine.game_id.in_(game_ids)).count()
        print(f"  {check_date}: {len(games)} games, {count} odds lines")
    else:
        print(f"  {check_date}: 0 games")

print("\nSample odds lines (first 5):")
lines = db.query(OddsLine).limit(5).all()
for ol in lines:
    game = db.query(Game).filter(Game.id == ol.game_id).first()
    player = db.query(Player).filter(Player.id == ol.player_id).first()
    print(f"  game_id={ol.game_id} game_date={game.date if game else '?'} player={player.name if player else '?'} stat={ol.stat_type} line={ol.line} book={ol.sportsbook}")

db.close()