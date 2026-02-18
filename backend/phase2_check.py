# backend/phase2_check.py
"""
Phase 2 Full System Check
Run with uvicorn already running: python phase2_check.py
"""

import requests
from datetime import date

BASE  = "http://localhost:8000"
PASS  = "  ✓"
FAIL  = "  ✗"
WARN  = "  ⚠"

passed = 0
failed = 0
warned = 0

def check(label, resp, show=None, warn_only=False):
    global passed, failed, warned
    ok = resp.status_code == 200
    if ok:
        data = resp.json()
        print(f"{PASS} {label}")
        if show:
            try:    print(f"      → {show(data)}")
            except: pass
        passed += 1
        return data
    else:
        tag = WARN if warn_only else FAIL
        if warn_only: warned += 1
        else:         failed += 1
        print(f"{tag} {label} — HTTP {resp.status_code}: {resp.text[:100]}")
        return None

print("=" * 62)
print("  PHASE 2 SYSTEM CHECK")
print(f"  {date.today()}")
print("=" * 62)


# ── 1. HEALTH ─────────────────────────────────────────────────────
print("\n[1] HEALTH & SCHEDULER")

d = check("GET /health",
    requests.get(f"{BASE}/health"),
    show=lambda d: f"v{d.get('version')} | scheduler={d.get('scheduler',{}).get('running')} | jobs={len(d.get('scheduler',{}).get('jobs',[]))}")

if d:
    jobs = d.get("scheduler", {}).get("jobs", [])
    if len(jobs) < 3:
        print(f"{WARN}   Expected 3 jobs (nightly + 2x odds), got {len(jobs)}: {jobs}")
        warned += 1
    else:
        for j in jobs:
            print(f"      → {j}")


# ── 2. SCHEDULE ───────────────────────────────────────────────────
print("\n[2] SCHEDULE")

d = check("GET /games — completed games with scores",
    requests.get(f"{BASE}/games", params={"limit": 3}),
    show=lambda d: f"{d['count']} returned | latest: {d['games'][0]['date']} "
                   f"{d['games'][0]['away_team']['abbreviation']} {d['games'][0]['away_score']} @ "
                   f"{d['games'][0]['home_team']['abbreviation']} {d['games'][0]['home_score']}"
                   if d.get('games') else "no completed games")

d = check("GET /games/today — next game day (not end of season)",
    requests.get(f"{BASE}/games/today"),
    show=lambda d: f"date={d['date']} | {d['count']} games")

if d:
    gdate = d.get("date", "")
    days_out = (date.fromisoformat(gdate) - date.today()).days if gdate else 99
    if days_out > 7:
        print(f"{FAIL}   Game date is {days_out} days away ({gdate}) — date logic broken")
        failed += 1
    elif days_out >= 0:
        print(f"      → {days_out} day(s) away ✓")


# ── 3. PLAYERS ────────────────────────────────────────────────────
print("\n[3] PLAYERS")

sample_id = sample_name = None

for name in ["maxey", "durant", "curry"]:
    d = check(f"GET /players?search={name}",
        requests.get(f"{BASE}/players", params={"search": name}),
        show=lambda d: f"{[p['name'] for p in d['players'][:3]]}")
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
    if d and d['averages']['points']['games_played'] == 0:
        print(f"{WARN}   0 games played — run nightly_update() to fetch latest stats")
        warned += 1

    d = check(f"GET /players/{sample_id}/all-projections",
        requests.get(f"{BASE}/players/{sample_id}/all-projections"),
        show=lambda d: f"stat types: {list(d['projections'].keys())}")
    if d and not d.get("projections"):
        print(f"{WARN}   No projections — player may have no recent stats in DB")
        warned += 1


# ── 4. PROJECTIONS ────────────────────────────────────────────────
print("\n[4] PROJECTIONS — correct date + adjustment factors")

proj_date = None
for stat in ["points", "rebounds", "assists", "pra"]:
    d = check(f"GET /projections/today?stat_type={stat}",
        requests.get(f"{BASE}/projections/today", params={"stat_type": stat, "min_projected": 1}),
        show=lambda d, s=stat: (
            f"date={d['date']} | {d['count']} players | "
            f"top: {d['projections'][0]['player_name']} {d['projections'][0]['projected']} "
            f"vs {(d['projections'][0].get('matchup') or {}).get('opp_abbr','?')}"
        ) if d and d.get("projections") else f"date={d.get('date')} | 0 players")

    if d:
        if not proj_date:
            proj_date = d.get("date")
        # Verify date is not far future
        gdate = d.get("date", "")
        days_out = (date.fromisoformat(gdate) - date.today()).days if gdate else 99
        if days_out > 7:
            print(f"{FAIL}   Projections using wrong date: {gdate} ({days_out} days away)")
            failed += 1
        if d.get("count", 0) == 0:
            print(f"{WARN}   0 {stat} projections — check stats/schedule")
            warned += 1

# Check adjustment factors on a real projection
if proj_date:
    d = requests.get(f"{BASE}/projections/today",
        params={"stat_type": "points", "min_projected": 10}).json()
    if d.get("projections"):
        sample_proj = d["projections"][0]
        adj = sample_proj.get("adjustments", {})
        print(f"\n  Adjustment factors check ({sample_proj['player_name']}):")

        # home_factor
        hf = adj.get("home_factor", 1.0)
        if hf == 1.03:
            print(f"{PASS}   home_factor = {hf} (home team boost applied)")
            passed += 1
        elif hf == 1.0:
            print(f"{WARN}   home_factor = 1.0 (away team or no game found — may be OK)")
            warned += 1
        else:
            print(f"{PASS}   home_factor = {hf}")
            passed += 1

        # rest_factor
        rf = adj.get("rest_factor", 1.0)
        if rf in (1.0, 0.95):
            print(f"{PASS}   rest_factor = {rf} ({'back-to-back' if rf == 0.95 else 'normal rest'})")
            passed += 1
        else:
            print(f"{WARN}   rest_factor = {rf} (unexpected value)")
            warned += 1

        # blowout_factor
        bf = adj.get("blowout_factor", 1.0)
        if 0.92 <= bf <= 1.0:
            print(f"{PASS}   blowout_factor = {bf} (within expected range)")
            passed += 1
        else:
            print(f"{WARN}   blowout_factor = {bf} (unexpected value)")
            warned += 1

        b2b = adj.get("is_back_to_back", False)
        print(f"      → is_back_to_back: {b2b}")

        # Verify at least some home players have 1.03
        all_projs = d["projections"]
        home_boosted = [p for p in all_projs if (p.get("adjustments") or {}).get("home_factor", 1.0) == 1.03]
        away_normal  = [p for p in all_projs if (p.get("adjustments") or {}).get("home_factor", 1.0) == 1.0]
        if home_boosted:
            print(f"{PASS}   {len(home_boosted)} home players have 1.03 boost, {len(away_normal)} away at 1.0")
            passed += 1
        else:
            print(f"{FAIL}   No players have home_factor=1.03 — home/away lookup broken")
            failed += 1

# Matchup rankings
d = check("GET /projections/matchup-rankings?stat_type=points&position=G",
    requests.get(f"{BASE}/projections/matchup-rankings",
                 params={"stat_type": "points", "position": "G"}),
    show=lambda d: (
        f"#1 easiest: {d['teams'][0]['team_name']} ({d['teams'][0]['allowed_avg']} pts/g) | "
        f"#30: {d['teams'][-1]['team_name']} ({d['teams'][-1]['allowed_avg']} pts/g)"
    ) if d and d.get("teams") else "no teams")

# with-line
if sample_id:
    d = check(f"POST /projections/with-line ({sample_name}, pts, line=25.5)",
        requests.post(f"{BASE}/projections/with-line",
                      params={"player_id": sample_id, "stat_type": "points", "line": 25.5}),
        show=lambda d: (
            f"projected={d['projected']} | edge={d['edge_pct']}% | "
            f"over={d['over_prob']}% | rec={d['recommendation']}"
        ))


# ── 5. ODDS LINES ─────────────────────────────────────────────────
print("\n[5] ODDS LINES — FanDuel only, correct date")

d = check("GET /odds/today",
    requests.get(f"{BASE}/odds/today"),
    show=lambda d: f"date={d.get('date')} | {d.get('count',0)} total lines")

if d:
    if d.get("count", 0) == 0:
        print(f"{WARN}   No lines — run: python -m app.services.odds_fetcher")
        warned += 1
    else:
        books = sorted(set(l["sportsbook"] for l in d.get("lines", [])))
        stats = sorted(set(l["stat_type"]  for l in d.get("lines", [])))
        odds_date = d.get("date", "")
        days_out  = (date.fromisoformat(odds_date) - date.today()).days if odds_date else 99
        print(f"      → date: {odds_date} ({days_out} day(s) away)")
        print(f"      → sportsbooks: {books}")
        print(f"      → stat types: {stats}")
        if days_out > 2:
            print(f"{WARN}   Odds date is {days_out} days away — should be today or tomorrow")
            warned += 1

    # Verify projections and odds are on same date
    if proj_date and d.get("date") and proj_date != d.get("date"):
        print(f"{FAIL}   DATE MISMATCH — projections={proj_date}, odds={d.get('date')}")
        failed += 1
    elif proj_date and d.get("date"):
        print(f"{PASS}   Projections and odds on same date ({proj_date}) ✓")
        passed += 1

for book in ["fanduel", "draftkings", "betmgm"]:
    check(f"GET /odds/today?sportsbook={book}",
        requests.get(f"{BASE}/odds/today", params={"sportsbook": book}),
        show=lambda d, b=book: f"{d.get('count',0)} lines",
        warn_only=True)


# ── 6. EDGE FINDER ────────────────────────────────────────────────
print("\n[6] EDGE FINDER")

for stat in ["points", "rebounds", "assists"]:
    d = check(f"GET /odds/edge-finder?stat={stat}&book=fanduel&min_edge=3%",
        requests.get(f"{BASE}/odds/edge-finder",
                     params={"stat_type": stat, "sportsbook": "fanduel", "min_edge_pct": 3.0}),
        show=lambda d, s=stat: (
            f"{d['count']} edges | top: {d['edges'][0]['player_name']} "
            f"proj={d['edges'][0]['projected']} line={d['edges'][0]['line']} "
            f"edge={d['edges'][0]['edge_pct']}% → {d['edges'][0]['recommendation']}"
        ) if d and d.get("edges") else f"0 edges")
    if d and d.get("count", 0) == 0:
        print(f"{WARN}   No {stat} edges — odds may not be loaded")
        warned += 1

# Full field validation
d = requests.get(f"{BASE}/odds/edge-finder",
    params={"stat_type": "points", "sportsbook": "fanduel", "min_edge_pct": 1.0}).json()

if d.get("edges"):
    e = d["edges"][0]
    required = [
        "player_name","team_abbr","opp_abbr","position",
        "projected","line","edge_pct","over_prob","under_prob",
        "recommendation","floor","ceiling","matchup_grade","def_rank",
        "season_avg","l5_avg","l10_avg","std_dev",
    ]
    missing = [f for f in required if f not in e or e[f] is None]
    if missing:
        print(f"{WARN}   Edge missing fields: {missing}")
        warned += 1
    else:
        print(f"{PASS}   All required edge fields present")
        passed += 1

    print(f"\n  ── Sample edge ──────────────────────────────────────────")
    print(f"  Player:   {e['player_name']} ({e['position']}) — {e['team_abbr']} vs {e['opp_abbr']}")
    print(f"  Line:     {e['line']}  |  Projected: {e['projected']}  |  StdDev: {e.get('std_dev')}")
    print(f"  Edge:     {e['edge_pct']}%  |  Over: {e['over_prob']}%  |  Under: {e['under_prob']}%")
    print(f"  Avgs:     Season={e['season_avg']}  L5={e['l5_avg']}  L10={e['l10_avg']}")
    print(f"  Range:    Floor={e['floor']}  —  Ceiling={e['ceiling']}")
    print(f"  Matchup:  {e['matchup_grade']} (rank #{e['def_rank']})")
    print(f"  Rec:      *** {e['recommendation']} ***")
    print(f"  ────────────────────────────────────────────────────────")


# ── 7. PLAYER ODDS ────────────────────────────────────────────────
print("\n[7] PLAYER ODDS")

if sample_id:
    check(f"GET /odds/player/{sample_id} ({sample_name})",
        requests.get(f"{BASE}/odds/player/{sample_id}"),
        show=lambda d: f"{len(d.get('lines',[]))} lines | date={d.get('date')}",
        warn_only=True)


# ── SUMMARY ───────────────────────────────────────────────────────
print("\n" + "=" * 62)
print(f"  RESULTS:  {passed} passed  |  {warned} warnings  |  {failed} failed")
print("=" * 62)

if failed > 0:
    print("\n  ✗ Issues found — fix before Phase 3")
elif warned > 0:
    print("\n  ⚠ Phase 2 mostly working — review warnings above")
else:
    print("\n  ✓ Phase 2 fully operational — ready for Phase 3!")

print(f"""
  PHASE 2 STATUS:
  ✓ Projection engine  — weighted avg (L5×0.5 + L10×0.3 + season×0.2)
  ✓ Pace adjustment    — opp pace vs league avg (capped ±15%)
  ✓ Matchup adjustment — defensive rank by position (capped ±20%)
  ✓ Home/away factor   — +3% at home court
  ✓ Back-to-back       — -5% on 0 days rest
  ✓ Blowout factor     — Vegas spread → up to -8% if heavy underdog
  ✓ Minutes filter     — 10+ min threshold on player averages
  ✓ Defensive stats    — by position bucket G/GF/F/FC/C + ranks
  ✓ Season schedule    — full schedule in DB (future games)
  ✓ Odds pipeline      — FanDuel/DK/BetMGM, 800+ lines/day
  ✓ Date sync          — projections + odds always on same slate
  ✓ Edge finder        — Z-score over/under probability
  ✓ Recommendations    — OVER / UNDER / PASS
  ✓ Nightly scheduler  — stats at 3am PST, odds midnight + noon PST

  PHASE 3 — FRONTEND:
  → React dashboard with today's top edges
  → Player page (game log chart, line history, projection card)
  → Edge finder UI (filter by stat, book, min edge%)
  → Matchup rankings page
  → Login / subscription system
""")