import { apiClient } from '../client'

export const projectionsAPI = {
  /**
   * Get all projections for today with filters
   */
  getToday: async (params?: {
    stat_type?: string
    min_projected?: number
    position?: string
  }) => {
    const { data } = await apiClient.get('/projections/today', { params })
    return data
  },

  /**
   * Get all stat type projections for a specific player
   */
  getAllPlayerProjections: async (playerId: number) => {
    const { data } = await apiClient.get(`/projections/player/${playerId}`)
    return data
  },

  /**
   * Run Monte Carlo simulation for a player
   */
  runMonteCarloSimulation: async (params: {
    player_id: number
    stat_type: string
    line: number
  }) => {
    const { data } = await apiClient.get('/projections/simulate', { params })
    return data
  },

  /**
   * Get projection for specific player and stat type
   */
  getPlayerProjection: async (playerId: number, statType: string) => {
    const { data } = await apiClient.get(`/projections/player/${playerId}/${statType}`)
    return data
  },
}