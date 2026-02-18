import { apiClient } from '../client'
import type { Player, GameLog } from '../types'

export const playersAPI = {
  /**
   * Search players by name
   */
  search: async (query: string): Promise<Player[]> => {
    const { data } = await apiClient.get('/players', {
      params: {
        search: query,
        limit: 50,
      },
    })
    return data
  },

  /**
   * Get player profile with details
   */
  getProfile: async (playerId: number): Promise<Player> => {
    const { data } = await apiClient.get(`/players/${playerId}/profile`)
    return data
  },

  /**
   * List players with optional filters
   */
  list: async (teamId?: number, position?: string): Promise<Player[]> => {
    const { data } = await apiClient.get('/players', {
      params: {
        team_id: teamId,
        position,
        limit: 100,
      },
    })
    return data
  },

  /**
   * Get player's game log
   */
  getGameLog: async (
    playerId: number,
    last?: number
  ): Promise<GameLog[]> => {
    const { data } = await apiClient.get(`/players/${playerId}/game-log`, {
      params: {
        last,
      },
    })
    return data
  },

  /**
   * Get player stats summary
   */
  getStats: async (playerId: number, statType?: string) => {
    const { data } = await apiClient.get(`/players/${playerId}/stats`, {
      params: {
        stat_type: statType,
      },
    })
    return data
  },
}