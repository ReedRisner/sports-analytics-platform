# backend/app/services/projection_engine.py
"""
Core projection engine.

For each player + stat type:
  1. Pull their game log from player_game_stats (MIN >= MIN_THRESHOLD only)
  2. Compute season avg, last-5 avg, last-10 avg
  3. Weighted projection = L5*0.50 + L10*0.30 + season*0.20
  4. Pace adjustment  — scale by (opp_pace / league_avg_pace)
  5. Matchup adjustment — scale by (opp_allowed / league_avg_allowed)
     using the team's defensive rank for the player's position bucket.
     The allowed averages in the DB are already computed with a minutes
     filter (MIN_DEF_THRESHOLD) so only meaningful performances count.
  6. Compute rolling std-dev → confidence band
  7. If a line is provided, compute edge % and over probability (Z-score)
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.player import Player, PlayerGameStats, Team, Game

# ── Constants ─────────────────────────────────────────────────────────────────
LEAGUE_AVG_PACE = 100.0

W_L5     = 0.50
W_L10    = 0.30
W_SEASON = 0.20

STD_WINDOW = 10

# Minimum minutes for a game to count in a player's OWN averages.
MIN_THRESHOLD = 10.0

# ── Adjustment caps — prevent runaway multipliers ─────────────────────────────
# Matchup factor capped at ±20% — opponent can't double a projection
MATCHUP_FACTOR_MIN = 0.80
MATCHUP_FACTOR_MAX = 1.20

# Pace factor capped at ±15%
PACE_FACTOR_MIN = 0.85
PACE_FACTOR_MAX = 1.15

# Home court advantage: ~3% boost at home (well documented in NBA data)
HOME_FACTOR = 1.03

# Back-to-back penalty: 0 days rest reduces output ~5%
B2B_FACTOR = 0.95

# Blowout risk penalty: max 8% reduction when game is likely a blowout
BLOWOUT_MAX_PENALTY = 0.08

POS_BUCKET = {
    'G':   'g',
    'G-F': 'gf',
    'F-G': 'gf',
    'F':   'f',
    'F-C': 'fc',
    'C-F': 'fc',
    'C':   'c',
}

STAT_CONFIG = {
    'points':   ('points',   'pts'),
    'rebounds': ('rebounds', 'reb'),
    'assists':  ('assists',  'ast'),
    'steals':   ('steals',   'stl'),
    'blocks':   ('blocks',   'blk'),
    'pra':      ('pra',      None),
    'pr':       ('pr',       None),
    'pa':       ('pa',       None),
    'ra':       ('ra',       None),
}

COMBO_PARTS = {
    'pra': ['pts', 'reb', 'ast'],
    'pr':  ['pts', 'reb'],
    'pa':  ['pts', 'ast'],
    'ra':  ['reb', 'ast'],
}


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class StatLine:
    season_avg:   float
    l5_avg:       float
    l10_avg:      float
    games_played: int


@dataclass
class MatchupContext:
    opp_team_id:    int
    opp_name:       str
    opp_abbr:       str
    opp_pace:       float
    allowed_avg:    Optional[float]   # allowed avg for THIS stat type
    def_rank:       Optional[int]     # rank for THIS stat type (1 = most permissive)
    pace_factor:    float
    matchup_factor: float
    matchup_grade:  str

    # Full defensive breakdown for the player's position bucket
    pts_allowed:    Optional[float] = None
    reb_allowed:    Optional[float] = None
    ast_allowed:    Optional[float] = None
    stl_allowed:    Optional[float] = None
    blk_allowed:    Optional[float] = None
    pts_rank:       Optional[int]   = None
    reb_rank:       Optional[int]   = None
    ast_rank:       Optional[int]   = None
    stl_rank:       Optional[int]   = None
    blk_rank:       Optional[int]   = None


@dataclass
class Projection:
    player_id:    int
    player_name:  str
    team_name:    str
    position:     str
    stat_type:    str

    season_avg:   float
    l5_avg:       float
    l10_avg:      float
    games_played: int

    projected:    float
    std_dev:      float
    floor:        float
    ceiling:      float

    matchup:      Optional[MatchupContext]

    # Situational adjustment factors (1.0 = no adjustment)
    home_factor:    float = 1.0
    rest_factor:    float = 1.0
    blowout_factor: float = 1.0
    is_back_to_back: bool = False

    line:           Optional[float] = None
    edge_pct:       Optional[float] = None
    over_prob:      Optional[float] = None
    under_prob:     Optional[float] = None
    recommendation: Optional[str]   = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _avg(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _normal_cdf(z: float) -> float:
    if z < -6: return 0.0
    if z > 6:  return 1.0
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    poly = t * (0.319381530
              + t * (-0.356563782
              + t * (1.781477937
              + t * (-1.821255978
              + t * 1.330274429))))
    p = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z) * poly
    return p if z >= 0 else 1.0 - p


def _matchup_grade(rank: Optional[int]) -> str:
    if rank is None: return "Unknown"
    if rank <= 5:    return "Elite"
    if rank <= 10:   return "Good"
    if rank <= 20:   return "Neutral"
    if rank <= 25:   return "Tough"
    return "Lockdown"


def _recommendation(edge_pct: float, over_prob: float) -> str:
    if edge_pct >= 5 and over_prob >= 0.55:  return "OVER"
    if edge_pct <= -5 and over_prob <= 0.45: return "UNDER"
    return "PASS"



# ── Situational adjustment helpers ───────────────────────────────────────────

def _home_away_factor(db: Session, player: Player, game_id: int) -> float:
    # Returns HOME_FACTOR if player is at home, 1.0 if away.
    if not game_id:
        return 1.0
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return 1.0
    return HOME_FACTOR if game.home_team_id == player.team_id else 1.0


def _rest_factor(db: Session, player: Player) -> float:
    # Checks if the most recent game was yesterday (back-to-back).
    # Returns B2B_FACTOR (0.95) if so, 1.0 otherwise.
    recent_games = (
        db.query(Game)
        .filter(
            ((Game.home_team_id == player.team_id) | (Game.away_team_id == player.team_id)),
            Game.home_score != None,
        )
        .order_by(desc(Game.date))
        .limit(2)
        .all()
    )
    if len(recent_games) < 2:
        return 1.0
    days_rest = (recent_games[0].date - recent_games[1].date).days
    return B2B_FACTOR if days_rest == 1 else 1.0


def _blowout_factor(db: Session, player: Player, opp_team_id: int) -> float:
    # Penalizes projections when the player's team is a heavy underdog.
    # Large point differential gap = likely blowout = early garbage time.
    # Max penalty is BLOWOUT_MAX_PENALTY (8%) when gap >= 20 pts.
    team = db.query(Team).filter(Team.id == player.team_id).first()
    opp  = db.query(Team).filter(Team.id == opp_team_id).first()
    if not team or not opp:
        return 1.0

    team_ppg     = _safe(team.points_per_game)
    team_opp_ppg = _safe(team.opp_points_per_game)
    opp_ppg      = _safe(opp.points_per_game)
    opp_opp_ppg  = _safe(opp.opp_points_per_game)

    if not team_ppg or not opp_ppg:
        return 1.0

    team_diff = team_ppg - team_opp_ppg   # positive = team is good
    opp_diff  = opp_ppg - opp_opp_ppg    # positive = opp is good

    # How much better is the opponent? Positive = bad for our player
    gap = opp_diff - team_diff
    if gap <= 8:
        return 1.0

    # Scale linearly: gap=8 → 0%, gap=20 → full BLOWOUT_MAX_PENALTY
    penalty_scale = min((gap - 8) / 12.0, 1.0)
    return 1.0 - (BLOWOUT_MAX_PENALTY * penalty_scale)


# ── League averages ───────────────────────────────────────────────────────────
def _league_avg_allowed(db: Session, stat_prefix: str, bucket: str) -> float:
    col_name = f"{stat_prefix}_allowed_{bucket}"
    teams = db.query(Team).all()
    vals = [_safe(getattr(t, col_name, None)) for t in teams
            if getattr(t, col_name, None) is not None]
    return _avg(vals) if vals else 1.0


def _league_avg_pace(db: Session) -> float:
    teams = db.query(Team).filter(Team.pace != None).all()
    paces = [_safe(t.pace) for t in teams if t.pace]
    return _avg(paces) if paces else LEAGUE_AVG_PACE


# ── Core stat retrieval — with minutes filter ─────────────────────────────────
def get_player_stat_lines(
    db:          Session,
    player_id:   int,
    stat_col:    str,
    limit:       int   = 82,
    min_minutes: float = MIN_THRESHOLD,
) -> list[float]:
    """
    Return stat values from the player's most recent qualifying games
    (MIN >= min_minutes), ordered most-recent-first.

    Filtering by minutes ensures:
    - Injury-limited appearances don't drag averages down
    - Garbage-time cameos don't inflate or deflate projections
    - The L5/L10 windows reflect actual full games played
    """
    rows = (
        db.query(PlayerGameStats, Game)
        .join(Game, PlayerGameStats.game_id == Game.id)
        .filter(
            PlayerGameStats.player_id == player_id,
            PlayerGameStats.minutes   >= min_minutes,
        )
        .order_by(desc(Game.date))
        .limit(limit)
        .all()
    )
    values = []
    for stat, _ in rows:
        v = getattr(stat, stat_col, None)
        if v is not None:
            values.append(_safe(v))
    return values


def compute_stat_averages(values: list[float]) -> StatLine:
    if not values:
        return StatLine(0.0, 0.0, 0.0, 0)
    return StatLine(
        season_avg   = _avg(values),
        l5_avg       = _avg(values[:5]),
        l10_avg      = _avg(values[:10]),
        games_played = len(values),
    )


# ── Matchup context ───────────────────────────────────────────────────────────
def get_matchup_context(
    db:          Session,
    player:      Player,
    opp_team_id: int,
    stat_type:   str,
) -> Optional[MatchupContext]:
    opp = db.query(Team).filter(Team.id == opp_team_id).first()
    if not opp:
        return None

    raw_pos     = (player.position or '').strip()
    bucket      = POS_BUCKET.get(raw_pos)
    league_pace = _league_avg_pace(db)

    opp_pace    = _safe(opp.pace, league_pace)
    pace_factor = opp_pace / league_pace if league_pace else 1.0

    allowed_avg    = None
    def_rank       = None
    matchup_factor = 1.0

    cfg         = STAT_CONFIG.get(stat_type, (None, None))
    stat_prefix = cfg[1]

    if stat_prefix and bucket:
        col_allowed    = f"{stat_prefix}_allowed_{bucket}"
        col_rank       = f"{stat_prefix}_rank_{bucket}"
        allowed_avg    = _safe(getattr(opp, col_allowed, None))
        def_rank       = getattr(opp, col_rank, None)
        league_avg     = _league_avg_allowed(db, stat_prefix, bucket)
        matchup_factor = (allowed_avg / league_avg) if league_avg else 1.0

    elif stat_type in COMBO_PARTS and bucket:
        factors = []
        for part in COMBO_PARTS[stat_type]:
            col_a        = f"{part}_allowed_{bucket}"
            part_allowed = _safe(getattr(opp, col_a, None))
            part_league  = _league_avg_allowed(db, part, bucket)
            if part_league:
                factors.append(part_allowed / part_league)
        matchup_factor = _avg(factors) if factors else 1.0
        def_rank       = getattr(opp, f"pts_rank_{bucket}", None)

    # ── Full defensive breakdown for this position bucket ─────────────────────
    def _get(stat, field):
        if not bucket:
            return None
        return getattr(opp, f"{stat}_{field}_{bucket}", None)

    return MatchupContext(
        opp_team_id    = opp.id,
        opp_name       = opp.name,
        opp_abbr       = opp.abbreviation or "",
        opp_pace       = opp_pace,
        allowed_avg    = allowed_avg,
        def_rank       = def_rank,
        pace_factor    = pace_factor,
        matchup_factor = matchup_factor,
        matchup_grade  = _matchup_grade(def_rank),
        # All 5 stats allowed to this position group
        pts_allowed    = _get("pts", "allowed"),
        reb_allowed    = _get("reb", "allowed"),
        ast_allowed    = _get("ast", "allowed"),
        stl_allowed    = _get("stl", "allowed"),
        blk_allowed    = _get("blk", "allowed"),
        pts_rank       = _get("pts", "rank"),
        reb_rank       = _get("reb", "rank"),
        ast_rank       = _get("ast", "rank"),
        stl_rank       = _get("stl", "rank"),
        blk_rank       = _get("blk", "rank"),
    )


# ── Main projection function ──────────────────────────────────────────────────
def project_player(
    db:          Session,
    player_id:   int,
    stat_type:   str,
    opp_team_id: Optional[int]   = None,
    line:        Optional[float] = None,
    min_minutes: float           = MIN_THRESHOLD,
    game_id:     Optional[int]   = None,
) -> Optional[Projection]:
    """
    Full projection for one player + stat type.

    Adjustments applied (in order):
      1. Weighted avg baseline (L5 x0.5 + L10 x0.3 + season x0.2)
      2. Matchup factor (opp defensive rank by position, capped ±20%)
      3. Pace factor (opp pace vs league avg, capped ±15%)
      4. Home/away factor (+3% at home)
      5. Rest/back-to-back factor (-5% on 0 days rest)
      6. Blowout risk factor (up to -8% if heavy underdog)
    """
    if stat_type not in STAT_CONFIG:
        return None

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return None

    stat_col = STAT_CONFIG[stat_type][0]
    values   = get_player_stat_lines(db, player_id, stat_col, min_minutes=min_minutes)

    # Need at least 3 qualifying games to make a meaningful projection
    if len(values) < 3:
        return None

    avgs = compute_stat_averages(values)

    base = (
        avgs.l5_avg     * W_L5 +
        avgs.l10_avg    * W_L10 +
        avgs.season_avg * W_SEASON
    )

    matchup  = None
    adjusted = base

    if opp_team_id:
        matchup = get_matchup_context(db, player, opp_team_id, stat_type)
        if matchup:
            # Cap both factors to prevent runaway projections
            pace_factor    = max(PACE_FACTOR_MIN,    min(PACE_FACTOR_MAX,    matchup.pace_factor))
            matchup_factor = max(MATCHUP_FACTOR_MIN, min(MATCHUP_FACTOR_MAX, matchup.matchup_factor))
            adjusted = base * pace_factor * matchup_factor

        # ── Situational adjustments ───────────────────────────────────────
        # Home/away: +3% at home court
        home_factor   = _home_away_factor(db, player, game_id)

        # Back-to-back: -5% on 0 days rest
        rest_factor   = _rest_factor(db, player)

        # Blowout risk: up to -8% if heavy underdog
        blowout_factor = _blowout_factor(db, player, opp_team_id)

        adjusted = adjusted * home_factor * rest_factor * blowout_factor

    recent = values[:STD_WINDOW]
    std    = _std_dev(recent)

    edge_pct   = None
    over_prob  = None
    under_prob = None
    rec        = None

    if line is not None and std > 0:
        edge_pct   = ((adjusted - line) / line * 100) if line else 0.0
        z          = (line - adjusted) / std
        over_prob  = 1.0 - _normal_cdf(z)
        under_prob = _normal_cdf(z)
        rec        = _recommendation(edge_pct, over_prob)
    elif line is not None:
        edge_pct   = ((adjusted - line) / line * 100) if line else 0.0
        over_prob  = 1.0 if adjusted > line else 0.0
        under_prob = 1.0 - over_prob
        rec        = "OVER" if adjusted > line else "UNDER"

    team = db.query(Team).filter(Team.id == player.team_id).first()

    # Collect final adjustment factors for transparency in the API response
    _home   = home_factor   if opp_team_id else 1.0
    _rest   = rest_factor   if opp_team_id else 1.0
    _blowout = blowout_factor if opp_team_id else 1.0

    return Projection(
        player_id    = player.id,
        player_name  = player.name,
        team_name    = team.name if team else "",
        position     = player.position or "",
        stat_type    = stat_type,
        season_avg   = round(avgs.season_avg, 2),
        l5_avg       = round(avgs.l5_avg, 2),
        l10_avg      = round(avgs.l10_avg, 2),
        games_played = avgs.games_played,
        projected    = round(adjusted, 2),
        std_dev      = round(std, 2),
        floor        = round(adjusted - std, 2),
        ceiling      = round(adjusted + std, 2),
        matchup      = matchup,
        home_factor     = round(_home, 3),
        rest_factor     = round(_rest, 3),
        blowout_factor  = round(_blowout, 3),
        is_back_to_back = (_rest < 1.0),
        line         = line,
        edge_pct     = round(edge_pct, 2)         if edge_pct   is not None else None,
        over_prob    = round(over_prob * 100, 1)   if over_prob  is not None else None,
        under_prob   = round(under_prob * 100, 1)  if under_prob is not None else None,
        recommendation = rec,
    )


# ── Bulk projection ───────────────────────────────────────────────────────────
def project_game_players(
    db:          Session,
    game_id:     int,
    stat_types:  list[str] = None,
    min_minutes: float     = MIN_THRESHOLD,
) -> list[Projection]:
    if stat_types is None:
        stat_types = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'pra']

    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return []

    results = []
    for team_id, opp_team_id in [
        (game.home_team_id, game.away_team_id),
        (game.away_team_id, game.home_team_id),
    ]:
        players = db.query(Player).filter(
            Player.team_id   == team_id,
            Player.is_active == True,
        ).all()

        for player in players:
            for stat in stat_types:
                proj = project_player(db, player.id, stat, opp_team_id,
                                      min_minutes=min_minutes)
                if proj and proj.projected > 0:
                    results.append(proj)

    return sorted(results, key=lambda p: p.projected, reverse=True)