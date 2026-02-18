import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { STAT_TYPES } from '@/lib/constants'
import { ArrowLeft, TrendingUp, Activity, BarChart3, Zap } from 'lucide-react'

export default function PlayerPage() {
  const { id } = useParams<{ id: string }>()
  const playerId = parseInt(id || '0')
  const navigate = useNavigate()
  
  const [selectedStat, setSelectedStat] = useState<string>('points')
  const [gameLogFilter, setGameLogFilter] = useState<'l5' | 'l10' | 'season'>('l10')

  // Fetch player projection from /projections/today
  const { data: projection, isLoading: projLoading } = useQuery({
    queryKey: ['player-projection', playerId, selectedStat],
    queryFn: async () => {
      const { data } = await apiClient.get('/projections/today', {
        params: { stat_type: selectedStat }
      })
      return data.find((p: any) => p.player_id === playerId)
    },
    enabled: !!playerId,
  })

  // Fetch player odds
  const { data: playerOdds } = useQuery({
    queryKey: ['player-odds', playerId, selectedStat],
    queryFn: async () => {
      const { data } = await apiClient.get(`/odds/player/${playerId}`)
      const lines = Array.isArray(data) ? data : data.lines || []
      return lines.find((line: any) => line.stat_type === selectedStat && line.sportsbook === 'fanduel')
    },
    enabled: !!playerId,
  })

  // Fetch Monte Carlo simulation if we have a line
  const { data: monteCarlo } = useQuery({
    queryKey: ['monte-carlo', playerId, selectedStat, playerOdds?.line],
    queryFn: async () => {
      const { data } = await apiClient.get('/projections/simulate', {
        params: {
          player_id: playerId,
          stat_type: selectedStat,
          line: playerOdds.line
        }
      })
      return data
    },
    enabled: !!playerId && !!playerOdds?.line,
  })

  // Fetch game log
  const { data: gameLog } = useQuery({
    queryKey: ['player-gamelog', playerId],
    queryFn: async () => {
      // This endpoint may not exist yet - handle gracefully
      try {
        const { data } = await apiClient.get(`/players/${playerId}/game-log`, {
          params: { last: 20 }
        })
        return data
      } catch {
        return []
      }
    },
    enabled: !!playerId,
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
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">Player not found</h2>
          <p className="text-muted-foreground">No projection data available for this player.</p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90"
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
                  <div className="flex items-center justify-between">
                    <div className={`text-2xl font-bold ${
                      playerOdds.recommendation === 'OVER' ? 'text-green-400' :
                      playerOdds.recommendation === 'UNDER' ? 'text-red-400' : 'text-gray-400'
                    }`}>
                      {playerOdds.recommendation}
                    </div>
                    {playerOdds.edge_pct !== undefined && (
                      <div className={`text-2xl font-bold font-mono ${
                        playerOdds.recommendation === 'OVER' ? 'text-green-400' :
                        playerOdds.recommendation === 'UNDER' ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        {playerOdds.edge_pct > 0 ? '+' : ''}{playerOdds.edge_pct.toFixed(1)}%
                      </div>
                    )}
                  </div>
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
              <span className="text-sm text-muted-foreground">Season Average</span>
              <span className="text-lg font-bold font-mono">{projection.season_avg.toFixed(1)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Last 5 Games</span>
              <span className="text-lg font-bold font-mono">{projection.l5_avg.toFixed(1)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Last 10 Games</span>
              <span className="text-lg font-bold font-mono">{projection.l10_avg.toFixed(1)}</span>
            </div>
            <div className="pt-3 border-t border-border flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Games Played</span>
              <span className="text-lg font-bold font-mono">{projection.games_played}</span>
            </div>
            {projection.std_dev && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Std Deviation</span>
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
                  <div className="grid grid-cols-2 gap-2">
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
            {projection.adjustments.is_back_to_back && (
              <div className="text-center p-3 rounded-lg bg-orange-500/20 border border-orange-500/50">
                <div className="text-xs text-muted-foreground mb-1">B2B Game</div>
                <div className="text-lg font-bold text-orange-400">Yes</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Monte Carlo Simulation */}
      {monteCarlo && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="text-xl font-bold mb-4">Monte Carlo Simulation (10,000 runs)</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="rounded-lg border border-border p-4">
              <div className="text-sm text-muted-foreground mb-2">Win Probabilities</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs">Over {monteCarlo.line}</span>
                  <span className="font-mono font-bold text-green-400">
                    {(monteCarlo.over_probability * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs">Under {monteCarlo.line}</span>
                  <span className="font-mono font-bold text-red-400">
                    {(monteCarlo.under_probability * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border p-4">
              <div className="text-sm text-muted-foreground mb-2">Expected Value</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs">Over EV</span>
                  <span className={`font-mono font-bold ${monteCarlo.expected_value.over_ev > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {monteCarlo.expected_value.over_ev > 0 ? '+' : ''}{monteCarlo.expected_value.over_ev.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs">Under EV</span>
                  <span className={`font-mono font-bold ${monteCarlo.expected_value.under_ev > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {monteCarlo.expected_value.under_ev > 0 ? '+' : ''}{monteCarlo.expected_value.under_ev.toFixed(2)}
                  </span>
                </div>
                <div className="pt-2 border-t border-border">
                  <div className="text-xs text-muted-foreground">Best Bet</div>
                  <div className="text-lg font-bold text-primary uppercase">{monteCarlo.expected_value.best_bet}</div>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border p-4">
              <div className="text-sm text-muted-foreground mb-2">Kelly Criterion</div>
              <div className="text-3xl font-bold font-mono text-primary">
                {(monteCarlo.expected_value.kelly_fraction * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                Suggested bankroll %
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border p-4">
            <div className="text-sm text-muted-foreground mb-3">Confidence Intervals</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(monteCarlo.confidence_intervals).map(([level, range]) => {
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

          <div className="rounded-lg border border-border p-4 mt-4">
            <div className="text-sm text-muted-foreground mb-3">Percentiles</div>
            <div className="grid grid-cols-5 gap-3">
              {Object.entries(monteCarlo.percentiles).map(([percentile, value]) => (
                <div key={percentile} className="text-center p-2 rounded bg-muted/50">
                  <div className="text-xs text-muted-foreground mb-1">{percentile}th</div>
                  <div className="text-lg font-mono font-bold">{(value as number).toFixed(1)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Game Log Chart - Coming Soon */}
      {gameLog && gameLog.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Performance History</h2>
            <div className="flex gap-2">
              {(['l5', 'l10', 'season'] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setGameLogFilter(filter)}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    gameLogFilter === filter
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted hover:bg-muted/80'
                  }`}
                >
                  {filter === 'l5' ? 'Last 5' : filter === 'l10' ? 'Last 10' : 'Season'}
                </button>
              ))}
            </div>
          </div>
          <div className="text-muted-foreground text-sm">
            Game log chart coming soon...
          </div>
        </div>
      )}
    </div>
  )
}