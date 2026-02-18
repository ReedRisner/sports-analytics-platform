# Sports Analytics Platform — Command Cheat Sheet

## Manual Update
```
cd C:\Users\reedl\OneDrive\Documents\sports-analytics-platform\backend
.\venv\Scripts\activate

python -c "from app.services.nba_fetcher import nightly_update; nightly_update()"

python -m app.services.odds_fetcher

python -c "from app.services.projection_grader import grade_yesterdays_projections; from app.database import SessionLocal; grade_yesterdays_projections(SessionLocal())"
```
---






## RESET DATABASE (wipe all data — do this before re-running fetcher)
Run in TablePlus SQL editor (Ctrl+Enter to execute):
```
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d sportsanalytics
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```
Then restart uvicorn (step 2 below) to recreate empty tables.

---

## START THE BACKEND SERVER
```
cd C:\Users\reedl\OneDrive\Documents\sports-analytics-platform\backend
.\venv\Scripts\activate
uvicorn app.main:app --reload
```
Keep this running in its own PowerShell window.
Test it: open http://localhost:8000/health in Chrome

---

## RUN THE DATA FETCHER
Open a second PowerShell window:
```
cd C:\Users\reedl\OneDrive\Documents\sports-analytics-platform\backend
.\venv\Scripts\activate
python -m app.services.nba_fetcher
```

---

## CHECK DATABASE HEALTH
```
cd C:\Users\reedl\OneDrive\Documents\sports-analytics-platform\backend
.\venv\Scripts\activate
python db_check.py
```

---

## SAVE TO GITHUB (run after every session)
```
cd C:\Users\reedl\OneDrive\Documents\sports-analytics-platform
git add .
git commit -m "your message here"
git push
```

---

## ACTIVATE VENV (run this every time you open a new PowerShell)
```
cd C:\Users\reedl\OneDrive\Documents\sports-analytics-platform\backend
.\venv\Scripts\activate
```
You should see (venv) appear in your terminal.

---

## INSTALL A NEW PACKAGE
Make sure venv is active, then:
```
pip install package-name
pip freeze > requirements.txt
```
Always update requirements.txt after installing anything new.

---

## FULL CLEAN RESET + REFETCH (do this in order)
1. Run DROP/CREATE in TablePlus
2. Start uvicorn in window 1
3. Run fetcher in window 2
4. Run db_check.py to verify
5. Git commit

---

## USEFUL PSQL (run in TablePlus SQL editor)
-- Count rows in every table
SELECT 'teams' as tbl, COUNT(*) FROM teams
UNION ALL SELECT 'players', COUNT(*) FROM players
UNION ALL SELECT 'games', COUNT(*) FROM games
UNION ALL SELECT 'player_game_stats', COUNT(*) FROM player_game_stats;

-- Top 10 PRA games
SELECT p.name, s.pra, s.points, s.rebounds, s.assists
FROM player_game_stats s
JOIN players p ON p.id = s.player_id
ORDER BY s.pra DESC LIMIT 10;

-- Find a specific player
SELECT * FROM players WHERE name ILIKE '%jokic%';

-- Check team stats
SELECT name, pace, offensive_rating, defensive_rating, points_per_game
FROM teams ORDER BY offensive_rating DESC;

-- Check game scores
SELECT g.date, t1.abbreviation as away, g.away_score,
       t2.abbreviation as home, g.home_score
FROM games g
JOIN teams t1 ON t1.id = g.away_team_id
JOIN teams t2 ON t2.id = g.home_team_id
ORDER BY g.date DESC LIMIT 10;
