# backend/phase2_check.py
"""
Phase 2 API Test — run with uvicorn already running.
Tests all major endpoints and prints results.

Usage:
    python phase2_check.py
"""

import requests
import json

BASE = "http://localhost:8000"

PASS = "  ✓"
FAIL = "  ✗"

def check(label, resp, show=None):
    if resp.status_code == 200:
        data = resp.json()
        print(f"{PASS} {label}")
        if show:
            print(f"      → {show(data)}")
        return data
    else:
        print(f"{FAIL} {label} — HTTP {resp.status_code}: {resp.text[:120]}")
        return None


print("=" * 60)
print("  PHASE 2 API CHECK")
print("=" * 60)

# ── Health ────────────────────────────────────────────────────
print("\n [HEALTH]")
check("GET /health",
      requests.get(f"{BASE}/health"),
      show=lambda d: d)

# ── Players ───────────────────────────────────────────────────
print("\n [PLAYERS]")

r = check("GET /players",
          requests.get(f"{BASE}/players", params={"limit": 5}),
          show=lambda d: f"{d['count']} returned, first: {d['players'][0]['name']}")

r = check("GET /players?search=herro",
          requests.get(f"{BASE}/players", params={"search": "herro"}),
          show=lambda d: f"Found: {[p['name'] for p in d['players']]}")

if r and r['players']:
    jokic_id = r['players'][0]['id']

    check(f"GET /players/{jokic_id}/profile",
          requests.get(f"{BASE}/players/{jokic_id}/profile"),
          show=lambda d: (
              f"Games: {d['averages']['points']['games_played']} | "
              f"PPG season: {d['averages']['points']['season_avg']} | "
              f"L5: {d['averages']['points']['l5_avg']} | "
              f"L10: {d['averages']['points']['l10_avg']}"
          ))

    check(f"GET /players/{jokic_id}/projection?stat_type=points",
          requests.get(f"{BASE}/players/{jokic_id}/projection", params={"stat_type": "points"}),
          show=lambda d: (
              f"Projected: {d['projected']} | "
              f"Floor: {d['floor']} | "
              f"Ceiling: {d['ceiling']} | "
              f"StdDev: {d['std_dev']}"
          ))

    check(f"GET /players/{jokic_id}/projection?stat_type=pra",
          requests.get(f"{BASE}/players/{jokic_id}/projection", params={"stat_type": "pra"}),
          show=lambda d: f"PRA projected: {d['projected']} | Floor: {d['floor']} | Ceiling: {d['ceiling']}")

    check(f"GET /players/{jokic_id}/all-projections",
          requests.get(f"{BASE}/players/{jokic_id}/all-projections"),
          show=lambda d: f"Stats covered: {list(d['projections'].keys())}")

# ── Games ─────────────────────────────────────────────────────
print("\n [GAMES]")

r = check("GET /games",
          requests.get(f"{BASE}/games", params={"limit": 5}),
          show=lambda d: f"{d['count']} games, most recent: {d['games'][0]['date']} — "
                         f"{d['games'][0]['away_team']['abbreviation']} {d['games'][0]['away_score']} @ "
                         f"{d['games'][0]['home_team']['abbreviation']} {d['games'][0]['home_score']}")

r_today = check("GET /games/today",
                requests.get(f"{BASE}/games/today", params={"stat_types": "points,rebounds,assists,pra"}),
                show=lambda d: f"Date: {d['date']} | Games: {d['count']}")

if r_today and r_today.get('games'):
    g = r_today['games'][0]
    game_id = g['id']
    home = g['home_team']['abbreviation']
    away = g['away_team']['abbreviation']
    home_players = g.get('home_players', [])
    away_players = g.get('away_players', [])
    print(f"      → {away} @ {home} | "
          f"Home roster projected: {len(home_players)} players | "
          f"Away: {len(away_players)} players")

    if home_players:
        top = home_players[0]
        pts = top['projections'].get('points', {})
        pra = top['projections'].get('pra', {})
        print(f"      → Top home player: {top['player_name']} | "
              f"PTS proj: {pts.get('projected')} ({pts.get('matchup_grade')}) | "
              f"PRA proj: {pra.get('projected')}")

    check(f"GET /games/{game_id}",
          requests.get(f"{BASE}/games/{game_id}"),
          show=lambda d: f"Game loaded: {d['away_team']['abbreviation']} @ {d['home_team']['abbreviation']}")

    check(f"GET /games/{game_id}/top-props?stat_type=points",
          requests.get(f"{BASE}/games/{game_id}/top-props", params={"stat_type": "points", "top_n": 5}),
          show=lambda d: f"Top 5 scorers: " + " | ".join(
              f"{p['player_name']} {p['projected']}" for p in d['players'][:5]
          ))

# ── Projections ───────────────────────────────────────────────
print("\n [PROJECTIONS]")

check("GET /projections/today?stat_type=points",
      requests.get(f"{BASE}/projections/today", params={"stat_type": "points", "min_projected": 10}),
      show=lambda d: f"Players with 10+ projected pts: {d['count']} | "
                     f"Top: {d['projections'][0]['player_name']} {d['projections'][0]['projected']}"
                     if d['projections'] else f"Count: {d['count']}")

check("GET /projections/today?stat_type=rebounds",
      requests.get(f"{BASE}/projections/today", params={"stat_type": "rebounds", "min_projected": 5}),
      show=lambda d: f"Players with 5+ proj reb: {d['count']} | "
                     f"Top: {d['projections'][0]['player_name']} {d['projections'][0]['projected']}"
                     if d['projections'] else f"Count: {d['count']}")

check("GET /projections/today?stat_type=pra",
      requests.get(f"{BASE}/projections/today", params={"stat_type": "pra", "min_projected": 20}),
      show=lambda d: f"Players with 20+ proj PRA: {d['count']} | "
                     f"Top: {d['projections'][0]['player_name']} {d['projections'][0]['projected']}"
                     if d['projections'] else f"Count: {d['count']}")

check("GET /projections/edge-finder",
      requests.get(f"{BASE}/projections/edge-finder"),
      show=lambda d: f"Players ranked: {d['count']} | "
                     f"Best matchup: {d['edges'][0]['player_name']} vs {d['edges'][0]['matchup']['opp_name']}"
                     if d.get('edges') else "No edges found")

check("GET /projections/matchup-rankings?stat_type=points&position=G",
      requests.get(f"{BASE}/projections/matchup-rankings", params={"stat_type": "points", "position": "G"}),
      show=lambda d: f"#1 easiest: {d['teams'][0]['team_name']} ({d['teams'][0]['allowed_avg']} pts/g) | "
                     f"#30 toughest: {d['teams'][-1]['team_name']} ({d['teams'][-1]['allowed_avg']} pts/g)")

check("GET /projections/matchup-rankings?stat_type=rebounds&position=C",
      requests.get(f"{BASE}/projections/matchup-rankings", params={"stat_type": "rebounds", "position": "C"}),
      show=lambda d: f"#1 easiest for Cs: {d['teams'][0]['team_name']} ({d['teams'][0]['allowed_avg']} reb/g)")

# ── With-line test (POST) ─────────────────────────────────────
print("\n [EDGE CALCULATION]")

# Test with Jokic if we found him, else skip
if r and r.get('players'):
    jokic_id = r['players'][0]['id']
    check("POST /projections/with-line (Jokic pts, line=27.5)",
          requests.post(f"{BASE}/projections/with-line", params={
              "player_id": jokic_id,
              "stat_type": "points",
              "line": 27.5,
          }),
          show=lambda d: (
              f"Projected: {d['projected']} | Line: {d['line']} | "
              f"Edge: {d['edge_pct']}% | Over%: {d['over_prob']}% | "
              f"Rec: {d['recommendation']}"
          ))

    check("POST /projections/with-line (Jokic pra, line=52.5)",
          requests.post(f"{BASE}/projections/with-line", params={
              "player_id": jokic_id,
              "stat_type": "pra",
              "line": 52.5,
          }),
          show=lambda d: (
              f"Projected: {d['projected']} | Line: {d['line']} | "
              f"Edge: {d['edge_pct']}% | Over%: {d['over_prob']}% | "
              f"Rec: {d['recommendation']}"
          ))

print("\n" + "=" * 60)
print("  Done! Check ✗ lines above for any issues.")
print("  Visit http://localhost:8000/docs for full interactive API.")
print("=" * 60)
