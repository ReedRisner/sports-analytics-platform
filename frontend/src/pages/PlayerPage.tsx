import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { STAT_TYPES } from '@/lib/constants'
import { ArrowLeft, TrendingUp, Activity, BarChart3, Zap } from 'lucide-react'
import GameLogChart from '@/components/projections/GameLogChart'
import { InfoTooltip } from '@/components/ui/InfoTooltip'
import { STAT_EXPLANATIONS } from '@/lib/stat-explanations'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts'

export default function PlayerPage() {
  const { id } = useParams<{ id: string }>()
  const playerId = parseInt(id || '0')
  const navigate = useNavigate()
  
  const [selectedStat, setSelectedStat] = useState<string>('points')
  const [gameLogFilter, setGameLogFilter] = useState<'l5' | 'l10' | 'vs_opp'>('l10')
  const [runMonteCarlo, setRunMonteCarlo] = useState(false) // Manual trigger

  // Fetch player projection from /projections/today
  const { data: projection, isLoading: projLoading, error: projError } = useQuery({
    queryKey: ['player-projection', playerId, selectedStat],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get('/projections/today', {
          params: { stat_type: selectedStat },
          timeout: 30000,
        })
        const projections = Array.isArray(data) ? data : data.projections || []
        return projections.find((p: any) => p.player_id === playerId)
      } catch (error) {
        console.error('Error fetching player projection:', error)
        return null
      }
    },
    enabled: !!playerId,
    retry: 1,
  })

  // Fetch player odds
  const { data: playerOdds } = useQuery({
    queryKey: ['player-odds', playerId, selectedStat],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get(`/odds/player/${playerId}`)
        const lines = Array.isArray(data) ? data : data.lines || []
        return lines.find((line: any) => line.stat_type === selectedStat && line.sportsbook === 'fanduel')
      } catch (error) {
        console.error('Error fetching player odds:', error)
        return null
      }
    },
    enabled: !!playerId,
    retry: 1,
  })

  // Fetch Monte Carlo simulation if we have a line AND user clicked the button
  const { data: monteCarlo, isLoading: monteCarloLoading, error: monteCarloError } = useQuery({
    queryKey: ['monte-carlo', playerId, selectedStat, playerOdds?.line],
    queryFn: async () => {
      console.log('Monte Carlo Request:', {
        player_id: playerId,
        stat_type: selectedStat,
        line: playerOdds.line
      })
      
      try {
        // Backend expects POST with query parameters (not body)
        const { data } = await apiClient.post('/projections/simulate', null, {
          params: {
            player_id: playerId,
            stat_type: selectedStat,
            line: playerOdds.line
          },
          timeout: 60000, // 60 second timeout
        })
        console.log('Monte Carlo Response:', data)
        console.log('Monte Carlo expected_value:', data.expected_value)
        console.log('Monte Carlo confidence_intervals:', data.confidence_intervals)
        console.log('Monte Carlo percentiles:', data.percentiles)
        return data
      } catch (error: any) {
        console.error('Monte Carlo Error:', error.response?.data)
        throw error
      }
    },
    enabled: !!playerId && !!playerOdds?.line && runMonteCarlo,
    retry: false,
  })

  // Fetch game log - endpoint may not exist yet
  const { data: gameLog } = useQuery({
    queryKey: ['player-gamelog', playerId],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get(`/players/${playerId}/game-log`, {
          params: { last: 20 }
        })
        return data
      } catch (error: any) {
        // Silently fail if endpoint doesn't exist yet (404)
        if (error.response?.status === 404) {
          return []
        }
        throw error
      }
    },
    enabled: !!playerId,
    retry: false, // Don't retry on 404
    meta: {
      errorMessage: 'Game log endpoint not available yet'
    }
  })

  if (projLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground">Loading player data...</p>
        </div>
      </div>
    )
  }

  if (!projection) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <h2 className="text-2xl font-bold mb-2">Player not found</h2>
          <p className="text-muted-foreground mb-4">
            {projError 
              ? 'Unable to load player data. The backend may be offline or the player may not have a projection for this stat type today.' 
              : 'No projection data available for this player.'}
          </p>
          <div className="text-sm text-muted-foreground mb-4">
            Player ID: {playerId} | Stat: {selectedStat}
          </div>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  const filteredGameLog = gameLog ? (gameLogFilter === 'l5' ? gameLog.slice(0, 5) : gameLogFilter === 'l10' ? gameLog.slice(0, 10) : gameLog) : []

  return (
    <div className="space-y-6 pb-12">
      {/* Back Button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      {/* Player Header */}
      <div className="rounded-xl border border-border bg-gradient-to-br from-card to-card/50 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">{projection.player_name}</h1>
            <div className="flex items-center gap-4 text-muted-foreground">
              <span className="text-sm font-medium">{projection.position}</span>
              <span className="text-sm">•</span>
              <span className="text-sm font-medium">{projection.team_name}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Stat Type Selector */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {Object.entries(STAT_TYPES).map(([value, label]) => (
          <button
            key={value}
            onClick={() => setSelectedStat(value)}
            className={`px-4 py-2 rounded-lg border whitespace-nowrap transition-colors ${
              selectedStat === value
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border hover:border-primary/50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Projection Card */}
        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Projection</h2>
          </div>

          <div>
            <div className="text-sm text-muted-foreground mb-1">Our Projection</div>
            <div className="text-5xl font-bold font-mono text-primary">
              {projection.projected.toFixed(1)}
            </div>
          </div>

          {playerOdds && (
            <div className="pt-4 border-t border-border">
              <div className="text-sm text-muted-foreground mb-2">FanDuel Line</div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border border-border p-3">
                  <div className="text-xs text-muted-foreground mb-1">OVER</div>
                  <div className="text-xl font-bold font-mono">{playerOdds.line.toFixed(1)}</div>
                  {playerOdds.over_odds && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {playerOdds.over_odds > 0 ? '+' : ''}{playerOdds.over_odds}
                    </div>
                  )}
                </div>
                <div className="rounded-lg border border-border p-3">
                  <div className="text-xs text-muted-foreground mb-1">UNDER</div>
                  <div className="text-xl font-bold font-mono">{playerOdds.line.toFixed(1)}</div>
                  {playerOdds.under_odds && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {playerOdds.under_odds > 0 ? '+' : ''}{playerOdds.under_odds}
                    </div>
                  )}
                </div>
              </div>

              {playerOdds.recommendation && (
                <div className={`mt-4 rounded-lg p-4 border ${
                  playerOdds.recommendation === 'OVER' ? 'bg-green-500/10 border-green-500/50' :
                  playerOdds.recommendation === 'UNDER' ? 'bg-red-500/10 border-red-500/50' :
                  'bg-gray-500/10 border-gray-500/50'
                }`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className={`text-2xl font-bold ${
                      playerOdds.recommendation === 'OVER' ? 'text-green-400' :
                      playerOdds.recommendation === 'UNDER' ? 'text-red-400' : 'text-gray-400'
                    }`}>
                      <InfoTooltip content={STAT_EXPLANATIONS.recommendation}>
                        {playerOdds.recommendation}
                      </InfoTooltip>
                    </div>
                    {playerOdds.edge_pct !== undefined && (
                      <div className={`text-2xl font-bold font-mono ${
                        playerOdds.recommendation === 'OVER' ? 'text-green-400' :
                        playerOdds.recommendation === 'UNDER' ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        <InfoTooltip content={STAT_EXPLANATIONS.edge}>
                          {playerOdds.edge_pct > 0 ? '+' : ''}{playerOdds.edge_pct.toFixed(1)}%
                        </InfoTooltip>
                      </div>
                    )}
                  </div>
                  {(playerOdds.over_prob !== undefined || playerOdds.under_prob !== undefined) && (
                    <div className="pt-2 border-t border-border/50">
                      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                        {playerOdds.over_prob !== undefined && (
                          <div>
                            <InfoTooltip content={STAT_EXPLANATIONS.over_prob}>
                              <span className="text-muted-foreground">Over Win %: </span>
                            </InfoTooltip>
                            <span className="font-mono font-bold text-green-400">
                              {playerOdds.over_prob > 1 
                                ? playerOdds.over_prob.toFixed(1) 
                                : (playerOdds.over_prob * 100).toFixed(1)}%
                            </span>
                          </div>
                        )}
                        {playerOdds.under_prob !== undefined && (
                          <div>
                            <InfoTooltip content={STAT_EXPLANATIONS.under_prob}>
                              <span className="text-muted-foreground">Under Win %: </span>
                            </InfoTooltip>
                            <span className="font-mono font-bold text-red-400">
                              {playerOdds.under_prob > 1 
                                ? playerOdds.under_prob.toFixed(1) 
                                : (playerOdds.under_prob * 100).toFixed(1)}%
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Expected Value */}
                      {playerOdds.expected_value !== undefined && (
                        <div className="flex items-center justify-between text-sm mb-2 pb-2 border-b border-border/50">
                          <InfoTooltip content={STAT_EXPLANATIONS.expected_value}>
                            <span className="text-muted-foreground">Expected Value:</span>
                          </InfoTooltip>
                          <span className={`font-mono font-bold ${
                            playerOdds.expected_value > 0 ? 'text-green-400' :
                            playerOdds.expected_value < 0 ? 'text-red-400' : ''
                          }`}>
                            {playerOdds.expected_value > 0 ? '+' : ''}${playerOdds.expected_value.toFixed(2)}
                          </span>
                        </div>
                      )}

                      {/* No-Vig Fair Odds */}
                      {((playerOdds.recommendation === 'OVER' && playerOdds.no_vig_fair_over !== undefined) ||
                        (playerOdds.recommendation === 'UNDER' && playerOdds.no_vig_fair_under !== undefined)) && (
                        <div className="flex items-center justify-between text-sm mb-2 pb-2 border-b border-border/50">
                          <span className="text-muted-foreground">No-Vig Fair Odds:</span>
                          <span className="font-mono font-bold">
                            {playerOdds.recommendation === 'OVER' && playerOdds.no_vig_fair_over
                              ? `${(playerOdds.no_vig_fair_over * 100).toFixed(1)}%`
                              : playerOdds.recommendation === 'UNDER' && playerOdds.no_vig_fair_under
                              ? `${(playerOdds.no_vig_fair_under * 100).toFixed(1)}%`
                              : '—'
                            }
                          </span>
                        </div>
                      )}

                      {/* Vig Percentage */}
                      {playerOdds.vig_percent !== undefined && (
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Sportsbook Vig:</span>
                          <span className="font-mono font-bold text-orange-400">
                            {playerOdds.vig_percent.toFixed(2)}%
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {projection.floor && projection.ceiling && (
            <div className="pt-4 border-t border-border">
              <div className="text-sm text-muted-foreground mb-3">Projected Range</div>
              <div className="flex items-center justify-between">
                <div className="text-center">
                  <div className="text-xs text-muted-foreground mb-1">Floor</div>
                  <div className="text-lg font-bold font-mono">{projection.floor.toFixed(1)}</div>
                </div>
                <div className="flex-1 mx-4">
                  <div className="h-2 bg-muted rounded-full" />
                </div>
                <div className="text-center">
                  <div className="text-xs text-muted-foreground mb-1">Ceiling</div>
                  <div className="text-lg font-bold font-mono">{projection.ceiling.toFixed(1)}</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Averages Card */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Averages</h2>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                <InfoTooltip content={STAT_EXPLANATIONS.season_avg}>
                  Season Average
                </InfoTooltip>
              </span>
              <span className="text-lg font-bold font-mono">{projection.season_avg.toFixed(1)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                <InfoTooltip content={STAT_EXPLANATIONS.l5_avg}>
                  Last 5 Games
                </InfoTooltip>
              </span>
              <span className="text-lg font-bold font-mono">{projection.l5_avg.toFixed(1)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                <InfoTooltip content={STAT_EXPLANATIONS.l10_avg}>
                  Last 10 Games
                </InfoTooltip>
              </span>
              <span className="text-lg font-bold font-mono">{projection.l10_avg.toFixed(1)}</span>
            </div>
            <div className="pt-3 border-t border-border flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                <InfoTooltip content={STAT_EXPLANATIONS.games_played}>
                  Games Played
                </InfoTooltip>
              </span>
              <span className="text-lg font-bold font-mono">{projection.games_played}</span>
            </div>
            {projection.std_dev && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  <InfoTooltip content={STAT_EXPLANATIONS.std_dev}>
                    Std Deviation
                  </InfoTooltip>
                </span>
                <span className="text-lg font-bold font-mono">{projection.std_dev.toFixed(2)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Matchup Card */}
        {projection.matchup && (
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-semibold">Matchup</h2>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Opponent</span>
                <span className="text-lg font-bold">{projection.matchup.opp_name}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Grade</span>
                <span className={`px-3 py-1 rounded-lg border font-semibold text-sm ${
                  projection.matchup.matchup_grade === 'Elite' ? 'bg-green-500/20 text-green-400 border-green-500' :
                  projection.matchup.matchup_grade === 'Good' ? 'bg-blue-500/20 text-blue-400 border-blue-500' :
                  projection.matchup.matchup_grade === 'Neutral' ? 'bg-gray-500/20 text-gray-400 border-gray-500' :
                  projection.matchup.matchup_grade === 'Tough' ? 'bg-orange-500/20 text-orange-400 border-orange-500' :
                  'bg-red-500/20 text-red-400 border-red-500'
                }`}>
                  {projection.matchup.matchup_grade}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-border">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Pace Factor</div>
                  <div className="text-lg font-bold font-mono">{projection.matchup.pace_factor.toFixed(2)}x</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Matchup Factor</div>
                  <div className="text-lg font-bold font-mono">{projection.matchup.matchup_factor.toFixed(2)}x</div>
                </div>
              </div>

              {projection.matchup.defense && (
                <div className="pt-3 border-t border-border">
                  <div className="text-xs text-muted-foreground mb-2">Defense vs Position</div>
                  <div className="grid grid-cols-3 gap-2">
                    {projection.matchup.defense.pts_allowed !== undefined && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">PTS: </span>
                        <span className="font-mono">{projection.matchup.defense.pts_allowed.toFixed(1)}</span>
                        {projection.matchup.defense.pts_rank && (
                          <span className="text-xs text-muted-foreground ml-1">(#{projection.matchup.defense.pts_rank})</span>
                        )}
                      </div>
                    )}
                    {projection.matchup.defense.reb_allowed !== undefined && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">REB: </span>
                        <span className="font-mono">{projection.matchup.defense.reb_allowed.toFixed(1)}</span>
                        {projection.matchup.defense.reb_rank && (
                          <span className="text-xs text-muted-foreground ml-1">(#{projection.matchup.defense.reb_rank})</span>
                        )}
                      </div>
                    )}
                    {projection.matchup.defense.ast_allowed !== undefined && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">AST: </span>
                        <span className="font-mono">{projection.matchup.defense.ast_allowed.toFixed(1)}</span>
                        {projection.matchup.defense.ast_rank && (
                          <span className="text-xs text-muted-foreground ml-1">(#{projection.matchup.defense.ast_rank})</span>
                        )}
                      </div>
                    )}
                    {projection.matchup.defense.stl_allowed !== undefined && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">STL: </span>
                        <span className="font-mono">{projection.matchup.defense.stl_allowed.toFixed(1)}</span>
                        {projection.matchup.defense.stl_rank && (
                          <span className="text-xs text-muted-foreground ml-1">(#{projection.matchup.defense.stl_rank})</span>
                        )}
                      </div>
                    )}
                    {projection.matchup.defense.blk_allowed !== undefined && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">BLK: </span>
                        <span className="font-mono">{projection.matchup.defense.blk_allowed.toFixed(1)}</span>
                        {projection.matchup.defense.blk_rank && (
                          <span className="text-xs text-muted-foreground ml-1">(#{projection.matchup.defense.blk_rank})</span>
                        )}
                      </div>
                    )}
                    {projection.matchup.defense.three_pointers_made_allowed != null && (
                      <div className="text-sm">
                        <span className="text-muted-foreground">3PM: </span>
                        <span className="font-mono">{projection.matchup.defense.three_pointers_made_allowed.toFixed(1)}</span>
                        {projection.matchup.defense.three_pointers_made_rank && (
                          <span className="text-xs text-muted-foreground ml-1">(#{projection.matchup.defense.three_pointers_made_rank})</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Adjustments */}
      {projection.adjustments && (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Projection Adjustments</h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {projection.adjustments.home_factor !== undefined && projection.adjustments.home_factor !== 1 && (
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-xs text-muted-foreground mb-1">Home/Away</div>
                <div className="text-lg font-bold font-mono">{projection.adjustments.home_factor.toFixed(2)}x</div>
              </div>
            )}
            {projection.adjustments.rest_factor !== undefined && projection.adjustments.rest_factor !== 1 && (
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-xs text-muted-foreground mb-1">Rest</div>
                <div className="text-lg font-bold font-mono">{projection.adjustments.rest_factor.toFixed(2)}x</div>
              </div>
            )}
            {projection.adjustments.form_factor !== undefined && projection.adjustments.form_factor !== 1 && (
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-xs text-muted-foreground mb-1">Form</div>
                <div className="text-lg font-bold font-mono">{projection.adjustments.form_factor.toFixed(2)}x</div>
              </div>
            )}
            {projection.adjustments.opp_strength !== undefined && projection.adjustments.opp_strength !== 1 && (
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <div className="text-xs text-muted-foreground mb-1">Opp Strength</div>
                <div className="text-lg font-bold font-mono">{projection.adjustments.opp_strength.toFixed(2)}x</div>
              </div>
            )}
            {projection.adjustments.is_back_to_back !== undefined && (
              <div className={`text-center p-3 rounded-lg ${
                projection.adjustments.is_back_to_back 
                  ? 'bg-orange-500/20 border border-orange-500/50'
                  : 'bg-green-500/10 border border-green-500/30'
              }`}>
                <div className="text-xs text-muted-foreground mb-1">
                  <InfoTooltip content={STAT_EXPLANATIONS.back_to_back}>
                    B2B Game
                  </InfoTooltip>
                </div>
                <div className={`text-lg font-bold ${
                  projection.adjustments.is_back_to_back ? 'text-orange-400' : 'text-green-400'
                }`}>
                  {projection.adjustments.is_back_to_back ? 'Yes' : 'No'}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Game Log Chart */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Performance History</h2>
          
          {/* Filter Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setGameLogFilter('l5')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                gameLogFilter === 'l5'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              Last 5
            </button>
            <button
              onClick={() => setGameLogFilter('l10')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                gameLogFilter === 'l10'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              Last 10
            </button>
            {projection?.matchup?.opp_abbr && (
              <button
                onClick={() => setGameLogFilter('vs_opp')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  gameLogFilter === 'vs_opp'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                vs {projection.matchup.opp_abbr}
              </button>
            )}
          </div>
        </div>



{/* Inline Game Log Bar Chart */}
{gameLog && gameLog.length > 0 && (
  <div className="space-y-4">
    {(() => {
      // Filter games based on selection
      let filteredGames = [...gameLog]
      
      if (gameLogFilter === 'l5') {
        filteredGames = filteredGames.slice(0, 5)
      } else if (gameLogFilter === 'l10') {
        filteredGames = filteredGames.slice(0, 10)
      } else if (gameLogFilter === 'vs_opp' && projection?.matchup?.opp_abbr) {
        // Filter to only games vs the upcoming opponent
        filteredGames = filteredGames.filter((game: any) => 
          game.opp_abbr === projection.matchup.opp_abbr
        )
      }
      
      const chartData = filteredGames
        .map((game: any, index: number) => {
          let value = 0
          // EXPLICIT HANDLING FOR EACH STAT TYPE
          if (selectedStat === 'threes') {
            value = Number(game.fg3m) || Number(game.three_pointers_made) || 0
          } else if (selectedStat === 'points') {
            value = Number(game.points) || 0
          } else if (selectedStat === 'rebounds') {
            value = Number(game.rebounds) || 0
          } else if (selectedStat === 'assists') {
            value = Number(game.assists) || 0
          } else if (selectedStat === 'steals') {
            value = Number(game.steals) || 0
          } else if (selectedStat === 'blocks') {
            value = Number(game.blocks) || 0
          } else if (selectedStat === 'pra') {
            value = Number(game.pra) || 0
          } else if (selectedStat === 'pr') {
            value = Number(game.pr) || 0
          } else if (selectedStat === 'pa') {
            value = Number(game.pa) || 0
          } else if (selectedStat === 'ra') {
            value = Number(game.ra) || 0
          }
          
          return {
            game: `G${filteredGames.length - index}`,
            date: (() => {
              const [year, month, day] = game.date.split('-')
              const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
              return `${months[Number(month) - 1]} ${Number(day)}`
            })(),
            opponent: game.opp_abbr,
            value,
            hit: playerOdds?.line ? value > playerOdds.line : undefined,
            result: game.result,
            isProjection: false,
          }
        })
        .reverse() // Reverse to show oldest to newest (left to right)
      
      // Add projection column if available
      if (projection?.projected && projection?.matchup?.opp_abbr) {
        chartData.push({
          game: 'Next',
          date: 'Projection',
          opponent: projection.matchup.opp_abbr,
          value: projection.projected,
          hit: playerOdds?.line ? projection.projected > playerOdds.line : undefined,
          result: '—',
          isProjection: true,
        })
      }
      
      // Calculate average (exclude projection)
      const historicalGames = chartData.filter((d: any) => !d.isProjection)
      const average = historicalGames.length > 0 
        ? historicalGames.reduce((sum: number, d: any) => sum + d.value, 0) / historicalGames.length 
        : 0
      
      return (
        <>
          {/* Stats Summary */}
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-lg border border-border p-3 bg-card">
              <div className="text-xs text-muted-foreground">Average</div>
              <div className="text-2xl font-bold font-mono">{average.toFixed(1)}</div>
            </div>
            {playerOdds?.line && historicalGames.length > 0 && (
              <>
                <div className="rounded-lg border border-border p-3 bg-card">
                  <div className="text-xs text-muted-foreground">Hit Rate</div>
                  <div className="text-2xl font-bold font-mono text-green-400">
                    {((historicalGames.filter((d: any) => d.hit).length / historicalGames.length) * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-card">
                  <div className="text-xs text-muted-foreground">Hits / Games</div>
                  <div className="text-2xl font-bold font-mono">
                    {historicalGames.filter((d: any) => d.hit).length} / {historicalGames.length}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Bar Chart */}
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis 
                  dataKey="game" 
                  stroke="hsl(var(--muted-foreground))"
                  style={{ fontSize: '12px' }}
                />
                <YAxis 
                  stroke="hsl(var(--muted-foreground))"
                  style={{ fontSize: '12px' }}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px'
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null
                    const data = payload[0].payload
                    
                    if (data.isProjection) {
                      return (
                        <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
                          <div className="font-semibold mb-2 text-primary">Next Game Projection</div>
                          <div className="space-y-1 text-sm">
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-muted-foreground">vs {data.opponent}</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-muted-foreground">
                                {selectedStat === 'threes' ? '3PM' : selectedStat.toUpperCase()}:
                              </span>
                              <span className="font-mono font-bold">{data.value.toFixed(1)}</span>
                            </div>
                            {playerOdds?.line && (
                              <div className="flex items-center justify-between gap-4 pt-2 border-t border-border">
                                <span className="text-muted-foreground">Line: {playerOdds.line}</span>
                                <span className={`font-bold ${data.hit ? 'text-green-400' : 'text-red-400'}`}>
                                  {data.hit ? 'Projected OVER' : 'Projected UNDER'}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    }
                    
                    return (
                      <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
                        <div className="font-semibold mb-2">{data.date}</div>
                        <div className="space-y-1 text-sm">
                          <div className="flex items-center justify-between gap-4">
                            <span className="text-muted-foreground">vs {data.opponent}</span>
                            <span className="font-bold">{data.result}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span className="text-muted-foreground">
                              {selectedStat === 'threes' ? '3PM' : selectedStat.toUpperCase()}:
                            </span>
                            <span className="font-mono font-bold">{data.value}</span>
                          </div>
                          {playerOdds?.line && (
                            <div className="flex items-center justify-between gap-4 pt-2 border-t border-border">
                              <span className="text-muted-foreground">Line: {playerOdds.line}</span>
                              <span className={`font-bold ${data.hit ? 'text-green-400' : 'text-red-400'}`}>
                                {data.hit ? '✓ HIT' : '✗ MISS'}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  }}
                />
                
                {/* Betting line */}
                {playerOdds?.line && (
                  <ReferenceLine 
                    y={playerOdds.line} 
                    stroke="#3b82f6"
                    strokeWidth={2}
                    label={{ 
                      value: `Line: ${playerOdds.line}`, 
                      position: 'right',
                      fill: '#3b82f6',
                      fontSize: 14,
                      fontWeight: 'bold'
                    }}
                  />
                )}
                
                {/* Average line */}
                <ReferenceLine 
                  y={average} 
                  stroke="#9ca3af"
                  strokeDasharray="5 5"
                  strokeWidth={1.5}
                  label={{ 
                    value: `Avg: ${average.toFixed(1)}`, 
                    position: 'left',
                    fill: '#9ca3af',
                    fontSize: 12
                  }}
                />
                
                {/* Bars colored by hit/miss or gray for projection */}
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry: any, index: number) => {
                    let color: string
                    
                    // Projection column is gray
                    if (entry.isProjection) {
                      color = 'hsl(var(--muted))' // Gray for projection
                    } else if (entry.hit === undefined) {
                      color = 'hsl(var(--primary))' // No line - use primary color
                    } else if (entry.hit) {
                      color = 'hsl(142.1 76.2% 36.3%)' // Green for hit
                    } else {
                      color = 'hsl(0 84.2% 60.2%)' // Red for miss
                    }
                    
                    return <Cell key={`cell-${index}`} fill={color} />
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          {playerOdds?.line && (
            <div className="flex items-center justify-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-500" />
                <span className="text-muted-foreground">Hit Over</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-red-500" />
                <span className="text-muted-foreground">Missed Over</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-muted" />
                <span className="text-muted-foreground">Next Game Projection</span>
              </div>
            </div>
          )}
        </>
      )
    })()}
  </div>
)}
      </div>

      {/* Monte Carlo Simulation */}
      {playerOdds?.line && (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Monte Carlo Simulation (10,000 runs)</h2>
            {!runMonteCarlo && !monteCarlo && (
              <button
                onClick={() => setRunMonteCarlo(true)}
                className="px-6 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity flex items-center gap-2"
              >
                <Zap className="w-4 h-4" />
                Run Simulation
              </button>
            )}
          </div>

          {!runMonteCarlo && !monteCarlo ? (
            <div className="py-12 text-center">
              <div className="mb-4">
                <Zap className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
              </div>
              <p className="text-muted-foreground mb-2">
                Click "Run Simulation" to analyze this prop with 10,000 Monte Carlo simulations
              </p>
              <p className="text-sm text-muted-foreground">
                This will show win probabilities, expected value, Kelly Criterion, and confidence intervals
              </p>
            </div>
          ) : monteCarloError ? (
            <div className="py-8">
              <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6">
                <div className="text-red-400 font-semibold mb-2">Failed to run simulation</div>
                <div className="text-red-400/80 text-sm mb-4">
                  {monteCarloError instanceof Error ? monteCarloError.message : 'Unknown error occurred'}
                </div>
                <div className="text-xs text-red-400/60 font-mono bg-black/20 p-3 rounded mb-3">
                  <div className="font-semibold mb-1">Request Info:</div>
                  Player ID: {playerId}<br />
                  Stat: {selectedStat}<br />
                  Line: {playerOdds?.line}
                </div>
                {(monteCarloError as any)?.response?.data?.detail && (
                  <div className="text-xs text-red-400/80 font-mono bg-black/20 p-3 rounded mb-3 max-h-60 overflow-auto">
                    <div className="font-semibold mb-2">Backend Response:</div>
                    <pre className="whitespace-pre-wrap text-xs">
                      {typeof (monteCarloError as any).response.data.detail === 'string'
                        ? (monteCarloError as any).response.data.detail
                        : JSON.stringify((monteCarloError as any).response.data.detail, null, 2)}
                    </pre>
                  </div>
                )}
                {(monteCarloError as any)?.response?.status && (
                  <div className="text-xs text-red-400/60 mb-3">
                    HTTP Status: {(monteCarloError as any).response.status}
                  </div>
                )}
                <button
                  onClick={() => {
                    setRunMonteCarlo(false)
                    // Wait a bit then allow retry
                    setTimeout(() => setRunMonteCarlo(false), 100)
                  }}
                  className="px-4 py-2 rounded-lg border border-red-500/50 text-red-400 hover:bg-red-500/10 text-sm"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : monteCarloLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
              <p className="text-muted-foreground text-center">
                Running 10,000 simulations...<br />
                <span className="text-sm">This may take 15-30 seconds</span>
              </p>
            </div>
          ) : monteCarlo ? (
            <>
              {/* Only render if we have the expected data structure */}
              {!monteCarlo.monte_carlo?.expected_value ? (
                <div className="py-8 text-center">
                  <div className="text-yellow-400 mb-2">⚠️ Incomplete simulation data</div>
                  <pre className="text-xs text-left max-w-2xl mx-auto overflow-auto bg-black/20 p-4 rounded">
                    {JSON.stringify(monteCarlo, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="rounded-lg border border-border p-4">
                      <div className="text-sm text-muted-foreground mb-2">
                        <InfoTooltip content="Probability of going over/under the line based on 10,000 simulations. 60%+ is strong, 70%+ is excellent.">
                          Win Probabilities
                        </InfoTooltip>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs">Over {monteCarlo.line}</span>
                          <span className="font-mono font-bold text-green-400">
                            {(monteCarlo.monte_carlo.over_probability * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs">Under {monteCarlo.line}</span>
                          <span className="font-mono font-bold text-red-400">
                            {(monteCarlo.monte_carlo.under_probability * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-lg border border-border p-4">
                      <div className="text-sm text-muted-foreground mb-2">
                        <InfoTooltip content={STAT_EXPLANATIONS.expected_value}>
                          Expected Value
                        </InfoTooltip>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs">Over EV</span>
                          <span className={`font-mono font-bold ${monteCarlo.monte_carlo?.expected_value?.over_ev > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {monteCarlo.monte_carlo?.expected_value?.over_ev > 0 ? '+' : ''}{monteCarlo.monte_carlo?.expected_value?.over_ev?.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs">Under EV</span>
                          <span className={`font-mono font-bold ${monteCarlo.monte_carlo?.expected_value?.under_ev > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {monteCarlo.monte_carlo?.expected_value?.under_ev > 0 ? '+' : ''}{monteCarlo.monte_carlo?.expected_value?.under_ev?.toFixed(2)}
                          </span>
                        </div>
                        <div className="pt-2 border-t border-border">
                          <div className="text-xs text-muted-foreground">Best Bet</div>
                          <div className="text-lg font-bold text-primary uppercase">{monteCarlo.monte_carlo?.expected_value?.best_bet}</div>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-lg border border-border p-4">
                      <div className="text-sm text-muted-foreground mb-2">
                        <InfoTooltip content={STAT_EXPLANATIONS.kelly_criterion}>
                          Kelly Criterion
                        </InfoTooltip>
                      </div>
                      <div className="text-3xl font-bold font-mono text-primary">
                        {((monteCarlo.monte_carlo?.expected_value?.kelly_fraction || 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground mt-2">
                        Suggested bankroll %
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border border-border p-4">
                    <div className="text-sm text-muted-foreground mb-3">
                      <InfoTooltip content={STAT_EXPLANATIONS.confidence_intervals}>
                        Confidence Intervals
                      </InfoTooltip>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {monteCarlo.monte_carlo.confidence_intervals && Object.entries(monteCarlo.monte_carlo.confidence_intervals).map(([level, range]) => {
                        const [low, high] = range as [number, number]
                        return (
                          <div key={level} className="text-center p-2 rounded bg-muted/50">
                            <div className="text-xs text-muted-foreground mb-1">{level}</div>
                            <div className="text-sm font-mono">
                              {low.toFixed(1)} - {high.toFixed(1)}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  <div className="rounded-lg border border-border p-4">
                    <div className="text-sm text-muted-foreground mb-3">
                      <InfoTooltip content="Shows the distribution of simulated outcomes. 50th = median (most likely result), 90th = optimistic outcome. Helps understand the range of possibilities.">
                        Percentiles
                      </InfoTooltip>
                    </div>
                    <div className="grid grid-cols-5 gap-3">
                      {monteCarlo.monte_carlo.percentiles && Object.entries(monteCarlo.monte_carlo.percentiles).map(([percentile, value]) => (
                        <div key={percentile} className="text-center p-2 rounded bg-muted/50">
                          <div className="text-xs text-muted-foreground mb-1">{percentile}th</div>
                          <div className="text-lg font-mono font-bold">{(value as number).toFixed(1)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  )
}