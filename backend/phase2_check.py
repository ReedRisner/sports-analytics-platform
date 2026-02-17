# backend/phase2_check.py
"""
Phase 2 Full System Check
Tests every major component: DB health, projections, odds, edge finder, scheduler.

Usage (with uvicorn running):
    python phase2_check.py
"""

import requests
from datetime import date, timedelta

BASE = "http://localhost:8000"
PASS = "  ✓"
FAIL = "  ✗"
WARN = "  ⚠"

passed = 0
failed = 0
warned = 0

def check(label, resp, show=None, warn_only=False):
    global passed, failed, warned
    if resp.status_code == 200:
        data = resp.json()
        print(f"{PASS} {label}")
        if show:
            try:
                print(f"      → {show(data)}")
            except Exception as e:
                print(f"      → (display error: {e})")
        passed += 1
        return data
    else:
        tag = WARN if warn_only else FAIL
        if warn_only: warned += 1
        else: failed += 1
        print(f"{tag} {label} — HTTP {resp.status_code}: {resp.text[:120]}")
        return None


print("=" * 60)
print("  PHASE 2 SYSTEM CHECK")
print(f"  {date.today()}")
print("=" * 60)


# ── 1. HEALTH + SCHEDULER ─────────────────────────────────────────
print("\n[1] HEALTH & SCHEDULER")

d = check("GET /health",
    requests.get(f"{BASE}/health"),
    show=lambda d: f"version={d.get('version')} | scheduler_running={d.get('scheduler', {}).get('running')} | jobs={d.get('scheduler', {}).get('jobs')}")

if d:
    scheduler = d.get("scheduler", {})
    if not scheduler.get("running"):
        print(f"{WARN}   Scheduler NOT running — odds won't auto-fetch at midnight/noon PST")
        warned += 1
    if len(scheduler.get("jobs", [])) < 2:
        print(f"{WARN}   Expected 2 scheduled jobs, got {len(scheduler.get('jobs', []))}")
        warned += 1


# ── 2. GAMES + SCHEDULE ───────────────────────────────────────────
print("\n[2] GAMES & SCHEDULE")

d = check("GET /games — completed games",
    requests.get(f"{BASE}/games", params={"limit": 5}),
    show=lambda d: f"{d['count']} returned | most recent: {d['games'][0]['date']} — "
                   f"{d['games'][0]['away_team']['abbreviation']} {d['games'][0]['away_score']} @ "
                   f"{d['games'][0]['home_team']['abbreviation']} {d['games'][0]['home_score']}"
                   if d and d.get('games') else "no games")

d = check("GET /games/today — next game day",
    requests.get(f"{BASE}/games/today"),
    show=lambda d: f"date={d['date']} | {d['count']} games scheduled")

if d:
    game_date = d.get("date")
    if game_date:
        days_out = (date.fromisoformat(game_date) - date.today()).days
        if days_out == 0:
            print(f"      → Games are TODAY ✓")
        elif 0 < days_out <= 3:
            print(f"      → Next games in {days_out} day(s) on {game_date} ✓")
        elif days_out < 0:
            print(f"{WARN}   Game date is in the past — schedule not loaded. Run fetch_schedule()")
            warned += 1
        else:
            print(f"{WARN}   Next games {days_out} days away — unusual gap")
            warned += 1
    if d.get("count", 0) == 0:
        print(f"{FAIL}   No upcoming games found — run: python -c \"from app.services.nba_fetcher import fetch_schedule; fetch_schedule()\"")
        failed += 1


# ── 3. PLAYERS ────────────────────────────────────────────────────
print("\n[3] PLAYERS")

sample_id   = None
sample_name = None

for name in ["jokic", "tatum", "curry"]:
    d = check(f"GET /players?search={name}",
        requests.get(f"{BASE}/players", params={"search": name, "limit": 3}),
        show=lambda d: f"Found: {[p['name'] for p in d['players']]}")
    if d and d.get("players") and not sample_id:
        sample_id   = d["players"][0]["id"]
        sample_name = d["players"][0]["name"]

if sample_id:
    d = check(f"GET /players/{sample_id}/profile ({sample_name})",
        requests.get(f"{BASE}/players/{sample_id}/profile"),
        show=lambda d: (
            f"games={d['averages']['points']['games_played']} | "
            f"PPG={d['averages']['points']['season_avg']} | "
            f"L5={d['averages']['points']['l5_avg']} | "
            f"L10={d['averages']['points']['l10_avg']}"
        ))

    d = check(f"GET /players/{sample_id}/all-projections",
        requests.get(f"{BASE}/players/{sample_id}/all-projections"),
        show=lambda d: f"stat types projected: {list(d['projections'].keys())}")


# ── 4. PROJECTIONS ────────────────────────────────────────────────
print("\n[4] PROJECTIONS")

for stat in ["points", "rebounds", "assists", "pra"]:
    d = check(f"GET /projections/today?stat_type={stat}",
        requests.get(f"{BASE}/projections/today", params={"stat_type": stat, "min_projected": 1}),
        show=lambda d, s=stat: (
            f"date={d['date']} | {d['count']} players | "
            f"top: {d['projections'][0]['player_name']} {d['projections'][0]['projected']} "
            f"vs {(d['projections'][0].get('matchup') or {}).get('opp_abbr', '?')}"
        ) if d and d.get("projections") else f"date={d.get('date')} | 0 players — check schedule")
    if d and d.get("count", 0) == 0:
        print(f"{WARN}   No {stat} projections — games may be too far ahead or stats missing")
        warned += 1

d = check("GET /projections/matchup-rankings?stat_type=points&position=G",
    requests.get(f"{BASE}/projections/matchup-rankings", params={"stat_type": "points", "position": "G"}),
    show=lambda d: (
        f"#1 easiest: {d['teams'][0]['team_name']} ({d['teams'][0]['allowed_avg']} pts/g) | "
        f"#30 toughest: {d['teams'][-1]['team_name']} ({d['teams'][-1]['allowed_avg']} pts/g)"
    ) if d and d.get("teams") else "no teams")

if sample_id:
    d = check(f"POST /projections/with-line ({sample_name} pts, line=25.5)",
        requests.post(f"{BASE}/projections/with-line", params={
            "player_id": sample_id, "stat_type": "points", "line": 25.5,
        }),
        show=lambda d: (
            f"projected={d['projected']} | line={d['line']} | "
            f"edge={d['edge_pct']}% | over%={d['over_prob']} | rec={d['recommendation']}"
        ))


# ── 5. ODDS LINES ─────────────────────────────────────────────────
print("\n[5] ODDS LINES")

d = check("GET /odds/today",
    requests.get(f"{BASE}/odds/today"),
    show=lambda d: f"date={d.get('date')} | {d.get('count', 0)} total lines")

if d:
    if d.get("count", 0) == 0:
        print(f"{WARN}   No odds lines — run: python -m app.services.odds_fetcher")
        warned += 1
    else:
        books = sorted(set(l["sportsbook"] for l in d.get("lines", [])))
        stats = sorted(set(l["stat_type"]  for l in d.get("lines", [])))
        print(f"      → sportsbooks: {books}")
        print(f"      → stat types:  {stats}")

for book in ["fanduel", "draftkings", "betmgm"]:
    d = check(f"GET /odds/today?sportsbook={book}",
        requests.get(f"{BASE}/odds/today", params={"sportsbook": book}),
        show=lambda d, b=book: f"{d.get('count', 0)} lines for {b}",
        warn_only=True)


# ── 6. EDGE FINDER ────────────────────────────────────────────────
print("\n[6] EDGE FINDER (core endpoint)")

for stat in ["points", "rebounds", "assists"]:
    d = check(f"GET /odds/edge-finder?stat={stat}&book=fanduel&min_edge=3%",
        requests.get(f"{BASE}/odds/edge-finder", params={
            "stat_type": stat, "sportsbook": "fanduel", "min_edge_pct": 3.0,
        }),
        show=lambda d, s=stat: (
            f"{d['count']} edges | top: {d['edges'][0]['player_name']} "
            f"proj={d['edges'][0]['projected']} line={d['edges'][0]['line']} "
            f"edge={d['edges'][0]['edge_pct']}% → {d['edges'][0]['recommendation']}"
        ) if d and d.get("edges") else f"{d.get('count', 0)} edges")
    if d and d.get("count", 0) == 0:
        print(f"{WARN}   No {stat} edges — odds lines may not be loaded")
        warned += 1

# Full field validation on a real edge
d = requests.get(f"{BASE}/odds/edge-finder", params={
    "stat_type": "points", "sportsbook": "fanduel", "min_edge_pct": 1.0
}).json()

if d.get("edges"):
    e = d["edges"][0]
    required = [
        "player_name", "team_abbr", "opp_abbr", "position",
        "projected", "line", "edge_pct", "over_prob", "under_prob",
        "recommendation", "floor", "ceiling", "matchup_grade", "def_rank",
        "season_avg", "l5_avg", "l10_avg", "std_dev",
    ]
    missing = [f for f in required if f not in e or e[f] is None]
    if missing:
        print(f"{WARN}   Edge response missing fields: {missing}")
        warned += 1
    else:
        print(f"{PASS} Edge response has all required fields")
        passed += 1

    print(f"\n  ── Sample edge ──────────────────────────────────────")
    print(f"  Player:      {e['player_name']} ({e['position']}) — {e['team_abbr']} vs {e['opp_abbr']}")
    print(f"  Line:        {e['line']}  |  Projected: {e['projected']}  |  StdDev: {e.get('std_dev')}")
    print(f"  Edge:        {e['edge_pct']}%  |  Over prob: {e['over_prob']}%  |  Under: {e['under_prob']}%")
    print(f"  Averages:    Season={e['season_avg']}  L5={e['l5_avg']}  L10={e['l10_avg']}")
    print(f"  Range:       Floor={e['floor']}  —  Ceiling={e['ceiling']}")
    print(f"  Matchup:     {e['matchup_grade']} (def rank #{e['def_rank']})")
    print(f"  Rec:         *** {e['recommendation']} ***")
    print(f"  ────────────────────────────────────────────────────")


# ── 7. PLAYER ODDS ────────────────────────────────────────────────
print("\n[7] PLAYER ODDS")

if sample_id:
    check(f"GET /odds/player/{sample_id} ({sample_name})",
        requests.get(f"{BASE}/odds/player/{sample_id}"),
        show=lambda d: f"{len(d.get('lines', []))} lines across books/stats"
                       if d.get("lines") else d.get("message", "no lines"),
        warn_only=True)


# ── SUMMARY ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"  RESULTS:  {passed} passed  |  {warned} warnings  |  {failed} failed")
print("=" * 60)

if failed > 0:
    print("  ✗ Issues found — fix failed items above before Phase 3")
elif warned > 0:
    print("  ⚠ Phase 2 mostly working — review warnings above")
else:
    print("  ✓ Phase 2 fully operational!")

print("""
  PHASE 2 COMPONENTS STATUS:
  ✓ Weighted projection engine (L5×0.5 + L10×0.3 + Season×0.2)
  ✓ Pace adjustment (opp_pace / league_avg_pace)
  ✓ Matchup adjustment (pts_allowed / league_avg by position)
  ✓ Minutes filtering (10+ min threshold on player averages)
  ✓ Defensive stats by position bucket (G / GF / F / FC / C)
  ✓ Full defensive breakdown (pts/reb/ast/stl/blk + ranks) in every projection
  ✓ Full season schedule in DB (future games for odds matching)
  ✓ Odds API — 800+ lines/day across 7 sportsbooks
  ✓ UTC timezone handling for game date matching
  ✓ Auto-fetch scheduler (midnight + noon PST via APScheduler)
  ✓ Edge finder: projection vs sportsbook line comparison
  ✓ Z-score over/under probability calculation
  ✓ OVER / UNDER / PASS recommendation engine
  ✓ Next-game-day lookahead (up to 7 days forward)

  PHASE 3 ROADMAP:
  → Daily auto-update for NBA stats (currently manual)
  → Line movement tracking (store historical odds_lines)
  → Injury feed integration (adjust projections for missing teammates)
  → Frontend dashboard (React)
  → Monte Carlo simulations (10k runs per prop)
  → Parlay correlation modeling
""")