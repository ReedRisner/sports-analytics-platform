# backend/debug_schedule.py
import requests

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
    'Referer': 'https://www.nba.com/',
})

resp = SESSION.get(
    "https://stats.nba.com/stats/scheduleleaguev2",
    params={"LeagueID": "00", "Season": "2025-26"},
    timeout=60,
)

print(f"Status code: {resp.status_code}")
print(f"Response length: {len(resp.text)}")
print(f"First 500 chars: {resp.text[:500]}")
print()

try:
    data = resp.json()
    print(f"Top-level keys: {list(data.keys())}")
    result_sets = data.get("resultSets", [])
    print(f"Number of result sets: {len(result_sets)}")
    for rs in result_sets:
        print(f"  name: '{rs.get('name')}' — {len(rs.get('rowSet', []))} rows")
except Exception as e:
    print(f"JSON parse error: {e}")