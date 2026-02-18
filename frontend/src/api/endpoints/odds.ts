import { apiClient } from '../client'
import type { Edge, OddsLine } from '../types'

/**
 * Odds API endpoints
 */
export const oddsAPI = {
  /**
   * Get edge finder results with filters
   */
  getEdgeFinder: async (
    statType?: string,
    sportsbook?: string,
    minEdgePct: number = 3.0,
    position?: string
  ): Promise<Edge[]> => {
    const { data } = await apiClient.get('/odds/edge-finder', {
      params: {
        stat_type: statType,
        sportsbook,
        min_edge_pct: minEdgePct,
        position,
      },
      timeout: 30000, // 30 second timeout for edge finder
    })
    // Backend returns { edges: [...] }, extract the array
    return Array.isArray(data) ? data : data.edges || []
  },

  /**
   * Get all odds lines for today
   */
  getTodayOdds: async (
    statType?: string,
    sportsbook?: string
  ): Promise<OddsLine[]> => {
    const { data } = await apiClient.get('/odds/today', {
      params: {
        stat_type: statType,
        sportsbook,
      },
    })
    return data
  },

  /**
   * Get odds for specific player
   */
  getPlayerOdds: async (playerId: number): Promise<OddsLine[]> => {
    const { data } = await apiClient.get(`/odds/player/${playerId}`)
    return data
  },

  /**
   * Get line movement history for a specific odds line
   */
  getLineMovement: async (oddsLineId: number) => {
    const { data } = await apiClient.get(`/odds/line-movement/${oddsLineId}`)
    return data
  },
}