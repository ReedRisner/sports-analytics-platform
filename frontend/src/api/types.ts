/**
 * Player entity from API
 */
export interface Player {
  id: number
  name: string
  position: string
  jersey: number
  team_id: number
  team_name: string
  team_abbr: string
  height?: string
  weight?: number
  photo_url?: string
}

/**
 * Team entity
 */
export interface Team {
  id: number
  name: string
  abbr: string
  city: string
  conference: string
  division: string
  pace?: number
  offensive_rating?: number
  defensive_rating?: number
}

/**
 * Projection from backend
 */
export interface Projection {
  player_id: number
  player_name: string
  team_name: string
  team_abbr?: string
  position: string
  stat_type: string
  projected: number
  season_avg: number
  l5_avg: number
  l10_avg: number
  std_dev: number
  floor: number
  ceiling: number
  games_played: number
  matchup?: MatchupContext
  line?: number
  edge_pct?: number
  over_prob?: number
  under_prob?: number
  recommendation?: 'OVER' | 'UNDER' | 'PASS'
  confidence?: number
  adjustments?: {
    home_factor: number
    rest_factor: number
    blowout_factor: number
    is_back_to_back: boolean
    days_rest: number
  }
}

/**
 * Matchup context for a projection
 */
export interface MatchupContext {
  opp_name: string
  opp_abbr: string
  opp_pace: number
  def_rank?: number
  matchup_grade: string
  pace_factor: number
  matchup_factor: number
  allowed_avg?: number
  is_home: boolean
  defense?: {
    pts_allowed?: number
    reb_allowed?: number
    ast_allowed?: number
    stl_allowed?: number
    blk_allowed?: number
    pts_rank?: number
    reb_rank?: number
    ast_rank?: number
    stl_rank?: number
    blk_rank?: number
  }
}

/**
 * Edge finder result
 */
export interface Edge {
  player_id: number
  player_name: string
  team_abbr: string
  opp_abbr: string
  position: string
  stat_type: string
  sportsbook: string
  line: number
  over_odds?: number
  under_odds?: number
  projected: number
  season_avg: number
  l5_avg: number
  l10_avg: number
  edge_pct: number
  over_prob: number
  under_prob: number
  recommendation: 'OVER' | 'UNDER' | 'PASS'
  floor: number
  ceiling: number
  std_dev: number
  matchup_grade?: string
  def_rank?: number
  confidence?: number
}

/**
 * Game log entry
 */
export interface GameLog {
  game_id: number
  date: string
  opponent: string
  opp_abbr: string
  home_away: 'home' | 'away'
  result: string
  minutes: number
  points: number
  rebounds: number
  assists: number
  steals: number
  blocks: number
  turnovers: number
  pra: number
  threes_made: number
  fg: string
  fg_pct: number
  fg3: string
  ft: string
  usage_rate?: number
  plus_minus?: number
  fantasy_pts: number
}

/**
 * Odds line from sportsbook
 */
export interface OddsLine {
  id: number
  player_id: number
  game_id: number
  stat_type: string
  sportsbook: string
  line_value: number
  over_odds: number
  under_odds: number
  timestamp: string
}

/**
 * Line movement tracking
 */
export interface LineMovement {
  id: number
  odds_line_id: number
  old_value: number
  new_value: number
  timestamp: string
  direction: 'up' | 'down'
}

/**
 * Auth response
 */
export interface AuthResponse {
  access_token: string
  token_type: string
  user: {
    id: number
    email: string
    tier: 'free' | 'premium'
  }
}

/**
 * User profile
 */
export interface User {
  id: number
  email: string
  tier: 'free' | 'premium'
  subscription_status?: string
  created_at: string
}

/**
 * Matchup ranking
 */
export interface MatchupRanking {
  team_id: number
  team_name: string
  team_abbr: string
  rank: number
  avg_allowed: number
  games: number
  grade: string
}

/**
 * API error response
 */
export interface APIError {
  detail: string
  status_code?: number
}