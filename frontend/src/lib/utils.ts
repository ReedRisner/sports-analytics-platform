import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind classes with proper precedence
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format date to readable string
 */
export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Format percentage with sign
 */
export function formatPercent(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
}

/**
 * Format stat value to fixed decimals
 */
export function formatStat(value: number, decimals: number = 1): string {
  return value.toFixed(decimals)
}

/**
 * Format odds (e.g., -110, +150)
 */
export function formatOdds(odds: number): string {
  return odds > 0 ? `+${odds}` : `${odds}`
}

/**
 * Convert American odds to implied probability
 */
export function oddsToProb(odds: number): number {
  if (odds > 0) {
    return 100 / (odds + 100)
  } else {
    return Math.abs(odds) / (Math.abs(odds) + 100)
  }
}

/**
 * Get team abbreviation color (can expand later)
 */
export function getTeamColor(abbr: string): string {
  const colors: Record<string, string> = {
    LAL: 'text-purple-400',
    BOS: 'text-green-400',
    GSW: 'text-yellow-400',
    MIA: 'text-red-400',
    // Add more as needed
  }
  return colors[abbr] || 'text-foreground'
}