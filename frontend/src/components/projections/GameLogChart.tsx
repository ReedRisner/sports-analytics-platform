import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend, Cell } from 'recharts'
//this is projections one
interface GameLog {
  game_id: number
  date: string
  opponent: string
  opp_abbr: string
  is_home: boolean
  result: string
  minutes: number
  points: number
  rebounds: number
  assists: number
  steals: number
  blocks: number
  fgm: number
  fga: number
  fg_pct: number
  fg3m: number
  fg3a: number
  fg3_pct: number
  ftm: number
  fta: number
  ft_pct: number
  oreb: number
  dreb: number
  turnovers: number
  plus_minus: number
  pra: number
  pr: number
  pa: number
  ra: number
  three_pointers_made: number
}
interface GameLogChartProps {
  games: GameLog[]
  statType: 'points' | 'rebounds' | 'assists' | 'steals' | 'blocks' | 'pra' | 'pr' | 'pa' | 'ra' | 'three_pointers_made'
  line?: number
  filter: 'l5' | 'l10' | 'vs_opp'
  opponentAbbr?: string
  nextGameProjection?: number  // Today's projection
}

export default function GameLogChart({ games, statType, line, filter, opponentAbbr, nextGameProjection }: GameLogChartProps) {
  const chartData = useMemo(() => {
    if (!games || games.length === 0) return []

    let filtered = [...games]

    // Filter based on selected range
    if (filter === 'l5') {
      filtered = filtered.slice(0, 5)
    } else if (filter === 'l10') {
      filtered = filtered.slice(0, 10)
    } else if (filter === 'vs_opp' && opponentAbbr) {
      filtered = filtered.filter(g => g.opponent === opponentAbbr)
    }

    // Reverse to show oldest to newest on chart
    filtered = filtered.reverse()

    const historicalData = filtered.map((game, index) => {
      let value: number
      
      if (statType === 'pra') {
        value = (game.points || 0) + (game.rebounds || 0) + (game.assists || 0)
      } else {
        value = game[statType] || 0
      }

      const hit = line ? value > line : undefined

      return {
        game: `G${index + 1}`,
        date: new Date(game.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        opponent: game.opponent,
        value: value,
        hit: hit,
        result: game.result,
        isProjection: false
      }
    })

    // Add next game projection
    if (nextGameProjection !== undefined) {
      const projectionHit = line ? nextGameProjection > line : undefined
      historicalData.push({
        game: 'Next',
        date: 'Projection',
        opponent: opponentAbbr || 'TBD',
        value: nextGameProjection,
        hit: projectionHit,
        result: '—',
        isProjection: true
      })
    }

    return historicalData
  }, [games, statType, line, filter, opponentAbbr, nextGameProjection])

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 border border-border rounded-lg bg-muted/20">
        <div className="text-center">
          <p className="text-muted-foreground mb-2">No game log data available</p>
          <p className="text-sm text-muted-foreground">
            {filter === 'vs_opp' 
              ? `No games found against ${opponentAbbr || 'this opponent'}`
              : 'No recent games found'
            }
          </p>
        </div>
      </div>
    )
  }

  // Calculate average excluding projection
  const historicalGames = chartData.filter(g => !g.isProjection)
  const average = historicalGames.length > 0 
    ? historicalGames.reduce((sum, g) => sum + g.value, 0) / historicalGames.length
    : 0

  console.log('GameLogChart DEBUG:', { line, average, chartDataLength: chartData.length })

  return (
    <div className="space-y-4">
      {/* Stats Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-border p-3 bg-card">
          <div className="text-xs text-muted-foreground">Average</div>
          <div className="text-2xl font-bold font-mono">{average.toFixed(1)}</div>
        </div>
        {line && historicalGames.length > 0 && (
          <>
            <div className="rounded-lg border border-border p-3 bg-card">
              <div className="text-xs text-muted-foreground">Hit Rate</div>
              <div className="text-2xl font-bold font-mono text-green-400">
                {((historicalGames.filter(g => g.hit).length / historicalGames.length) * 100).toFixed(0)}%
              </div>
            </div>
            <div className="rounded-lg border border-border p-3 bg-card">
              <div className="text-xs text-muted-foreground">Hits / Games</div>
              <div className="text-2xl font-bold font-mono">
                {historicalGames.filter(g => g.hit).length} / {historicalGames.length}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Chart */}
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
                          <span className="text-muted-foreground">{statType.toUpperCase()}:</span>
                          <span className="font-mono font-bold">{data.value.toFixed(1)}</span>
                        </div>
                        {line && (
                          <div className="flex items-center justify-between gap-4 pt-2 border-t border-border">
                            <span className="text-muted-foreground">Line: {line}</span>
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
                        <span className="text-muted-foreground">{statType.toUpperCase()}:</span>
                        <span className="font-mono font-bold">{data.value}</span>
                      </div>
                      {line && (
                        <div className="flex items-center justify-between gap-4 pt-2 border-t border-border">
                          <span className="text-muted-foreground">Line: {line}</span>
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
            <Legend 
              wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
            />
            
            {/* Betting line - prominent horizontal line */}
            {line !== undefined && line !== null && (
              <ReferenceLine 
                y={line} 
                stroke="#3b82f6"
                strokeWidth={2}
                label={{ 
                  value: `Line: ${line}`, 
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
              {chartData.map((entry, index) => {
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

      {line && (
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
    </div>
  )
}