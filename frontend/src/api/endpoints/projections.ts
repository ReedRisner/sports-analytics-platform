import { apiClient } from '../client'
import type { Projection, MatchupRanking } from '../types'

/**
 * Projections API endpoints
 */
export const projectionsAPI = {
  /**
   * Get today's projections with optional filters
   */
  getToday: async (
    statType?: string,
    minProjected: number = 0
  ): Promise<Projection[]> => {
    const { data } = await apiClient.get('/projections/today', {
      params: {
        stat_type: statType,
        min_projected: minProjected,
      },
    })
    return data
  },

  /**
   * Get projection for specific player
   */
  getPlayerProjection: async (
    playerId: number,
    statType: string,
    oppTeamId?: number,
    line?: number
  ): Promise<Projection> => {
    const { data } = await apiClient.get(`/players/${playerId}/projection`, {
      params: {
        stat_type: statType,
        opp_team_id: oppTeamId,
        line,
      },
    })
    return data
  },

  /**
   * Get all projections for a player (all stat types)
   */
  getAllPlayerProjections: async (
    playerId: number,
    oppTeamId?: number
  ): Promise<Projection[]> => {
    const { data } = await apiClient.get(`/players/${playerId}/all-projections`, {
      params: {
        opp_team_id: oppTeamId,
      },
    })
    return data
  },

  /**
   * Get matchup rankings (softest/hardest defenses by position)
   */
  getMatchupRankings: async (
    statType: string,
    position?: string
  ): Promise<MatchupRanking[]> => {
    const { data } = await apiClient.get('/projections/matchup-rankings', {
      params: {
        stat_type: statType,
        position,
      },
    })
    return data
  },
}