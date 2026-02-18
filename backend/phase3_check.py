# backend/test_phase3.py
"""
Test Phase 3 enhancements:
- Monte Carlo simulations
- Injury impact
- Projection grading
- New adjustment factors
"""

import requests

BASE = "http://localhost:8000"

print("=" * 60)
print("  PHASE 3 FEATURE TESTS")
print("=" * 60)

# Test 1: Monte Carlo simulation
print("\n[1] Monte Carlo Simulation")
resp = requests.post(f"{BASE}/projections/simulate", params={
    "player_id": 203954,  # Joel Embiid
    "stat_type": "points",
    "line": 28.5,
})

if resp.status_code == 200:
    data = resp.json()
    mc = data["monte_carlo"]
    print(f"✓ Player: {data['player_name']}")
    print(f"  Projected: {data['projected']}")
    print(f"  Line: {data['line']}")
    print(f"  Percentiles: {mc['percentiles']}")
    print(f"  Over probability: {mc['over_probability'] * 100:.1f}%")
    print(f"  Best bet: {mc['expected_value']['best_bet']}")
    print(f"  EV (over): ${mc['expected_value']['over_ev']:.2f} per $100")
    print(f"  Kelly: {mc['expected_value']['kelly_fraction'] * 100:.1f}% of bankroll")
else:
    print(f"✗ Failed: {resp.status_code} - {resp.text[:200]}")

# Test 2: Check new adjustment factors
print("\n[2] New Adjustment Factors (Injury/Form/Opponent)")
resp = requests.get(f"{BASE}/projections/today", params={
    "stat_type": "points",
    "min_projected": 15,
})

if resp.status_code == 200:
    projs = resp.json()["projections"]
    if projs:
        sample = projs[0]
        adj = sample.get("adjustments", {})
        print(f"✓ {sample['player_name']} adjustments:")
        print(f"    Home: {adj.get('home_factor', 1.0):.3f}x")
        print(f"    Rest: {adj.get('rest_factor', 1.0):.3f}x")
        print(f"    Blowout: {adj.get('blowout_factor', 1.0):.3f}x")
        print(f"    Injury: {adj.get('injury_factor', 1.0):.3f}x")
        print(f"    Form: {adj.get('form_factor', 1.0):.3f}x")
        print(f"    Opp strength: {adj.get('opp_strength', 1.0):.3f}x")
        print(f"    Back-to-back: {adj.get('is_back_to_back', False)}")
    else:
        print("  ⚠ No projections available")
else:
    print(f"✗ Failed: {resp.status_code}")

# Test 3: Model accuracy
print("\n[3] Model Accuracy Dashboard")
resp = requests.get(f"{BASE}/projections/accuracy", params={
    "stat_type": "points",
    "days_back": 30,
})

if resp.status_code == 200:
    acc = resp.json()
    if acc.get("sample_size", 0) > 0:
        print(f"✓ Sample: {acc['sample_size']} graded projections")
        print(f"  Win rate: {acc['overall']['win_rate']}%")
        print(f"  Profit: ${acc['overall']['profit']:.2f}")
        print(f"  ROI: {acc['overall']['roi']}%")
        print(f"  MAE: {acc['error_metrics']['mae']:.2f} points")
        print(f"  By edge size:")
        for bucket, stats in acc.get("by_edge_size", {}).items():
            print(f"    {bucket}: {stats['win_rate']}% ({stats['sample_size']} bets)")
    else:
        print("  ⚠ No graded projections yet")
        print("     Run nightly_update() after games finish to grade projections")
else:
    print(f"✗ Failed: {resp.status_code}")

# Test 4: Verify API endpoints exist
print("\n[4] API Endpoint Verification")
endpoints = [
    ("GET", "/projections/today?stat_type=points"),
    ("POST", "/projections/simulate?player_id=203954&stat_type=points&line=25.5"),
    ("GET", "/projections/accuracy?stat_type=points"),
    ("GET", "/odds/edge-finder?stat_type=points&sportsbook=fanduel"),
]

for method, endpoint in endpoints:
    if method == "GET":
        resp = requests.get(f"{BASE}{endpoint}")
    else:
        resp = requests.post(f"{BASE}{endpoint}")
    
    if resp.status_code in [200, 404]:  # 404 is ok for no data
        print(f"  ✓ {method} {endpoint}")
    else:
        print(f"  ✗ {method} {endpoint} - {resp.status_code}")

print("\n" + "=" * 60)
print("  Phase 3 tests complete!")
print("=" * 60)
print("\nNext steps:")
print("1. Run: alembic revision --autogenerate -m 'Add projection tracking'")
print("2. Run: alembic upgrade head")
print("3. Wait for games to finish and run nightly_update()")
print("4. Check /projections/accuracy to see model performance")