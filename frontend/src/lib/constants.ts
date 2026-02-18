/**
 * Stat types available in the app
 */
export const STAT_TYPES = {
  points: 'Points',
  rebounds: 'Rebounds',
  assists: 'Assists',
  steals: 'Steals',
  blocks: 'Blocks',
  threes: '3PM',
  pra: 'PRA',
  pr: 'P+R',
  pa: 'P+A',
  ra: 'R+A',
} as const

export type StatType = keyof typeof STAT_TYPES

/**
 * Edge color classes based on strength and direction
 */
export const EDGE_COLORS = {
  strong: {
    over: 'bg-green-500/20 border-green-500 text-green-400',
    under: 'bg-red-500/20 border-red-500 text-red-400',
  },
  moderate: {
    over: 'bg-green-500/10 border-green-600 text-green-500',
    under: 'bg-red-500/10 border-red-600 text-red-500',
  },
  weak: 'bg-gray-500/10 border-gray-600 text-gray-400',
  pass: 'bg-gray-800/50 border-gray-700 text-gray-500',
}

/**
 * Stat-specific colors for badges and charts
 */
export const STAT_COLORS: Record<string, string> = {
  points: 'text-blue-400',
  rebounds: 'text-orange-400',
  assists: 'text-purple-400',
  steals: 'text-cyan-400',
  blocks: 'text-pink-400',
  threes: 'text-green-400',
  pra: 'text-yellow-400',
  pr: 'text-green-400',
  pa: 'text-indigo-400',
  ra: 'text-rose-400',
}

/**
 * Matchup grade colors
 */
export const GRADE_COLORS: Record<string, string> = {
  Elite: 'bg-green-500/20 text-green-400 border-green-500',
  Good: 'bg-blue-500/20 text-blue-400 border-blue-500',
  Neutral: 'bg-gray-500/20 text-gray-400 border-gray-500',
  Tough: 'bg-orange-500/20 text-orange-400 border-orange-500',
  Lockdown: 'bg-red-500/20 text-red-400 border-red-500',
}

/**
 * Supported sportsbooks
 */
export const SPORTSBOOKS = [
  { value: 'fanduel', label: 'FanDuel' },
  { value: 'draftkings', label: 'DraftKings' },
  { value: 'betmgm', label: 'BetMGM' },
  { value: 'bet365', label: 'Bet365' },
] as const

/**
 * Position filters
 */
export const POSITIONS = [
  { value: 'G', label: 'Guard' },
  { value: 'F', label: 'Forward' },
  { value: 'C', label: 'Center' },
] as const

/**
 * Edge thresholds for classification
 */
export const EDGE_THRESHOLDS = {
  strong: 10, // >= 10% edge
  moderate: 5, // >= 5% edge
  weak: 3, // >= 3% edge
  pass: 0, // < 3% edge
} as const