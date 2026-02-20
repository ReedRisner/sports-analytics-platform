import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

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
  statType: string
  line?: number
  filter?: 'l5' | 'l10' | 'vs_opp'
  opponentAbbr?: string
  nextGameProjection?: number
}

export function GameLogChart({ 
  games, 
  statType, 
  line = 0,
  filter = 'l10',
  opponentAbbr,
  nextGameProjection 
}: GameLogChartProps) {
  
  if (!games || games.length === 0) {
    return <div className="text-center py-12 text-muted-foreground">No game data available</div>
  }
  
  // Filter games
  let filteredGames = [...games]
  if (filter === 'l5') filteredGames = filteredGames.slice(0, 5)
  else if (filter === 'l10') filteredGames = filteredGames.slice(0, 10)
  else if (filter === 'vs_opp' && opponentAbbr) filteredGames = filteredGames.filter(g => g.opp_abbr === opponentAbbr)

  // Map to chart data
  const chartData = filteredGames.map((game) => {
    let value = 0
    
    // Use if/else for reliability
    if (statType === 'points') value = Number(game.points) || 0
    else if (statType === 'rebounds') value = Number(game.rebounds) || 0
    else if (statType === 'assists') value = Number(game.assists) || 0
    else if (statType === 'steals') value = Number(game.steals) || 0
    else if (statType === 'blocks') value = Number(game.blocks) || 0
    else if (statType === 'threes') value = Number(game.fg3m) || Number(game.three_pointers_made) || 0
    else if (statType === 'pra') value = Number(game.pra) || (Number(game.points) + Number(game.rebounds) + Number(game.assists)) || 0
    else if (statType === 'pr') value = Number(game.pr) || (Number(game.points) + Number(game.rebounds)) || 0
    else if (statType === 'pa') value = Number(game.pa) || (Number(game.points) + Number(game.assists)) || 0
    else if (statType === 'ra') value = Number(game.ra) || (Number(game.rebounds) + Number(game.assists)) || 0
    else value = Number(game.points) || 0

    return {
      date: new Date(game.date).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' }),
      opponent: game.opp_abbr,
      value,
      hit: line > 0 ? value > line : false,
      result: game.result,
      isHome: game.is_home ? 'vs' : '@',
    }
  }).reverse()

  if (nextGameProjection && opponentAbbr) {
    chartData.push({
      date: 'Proj',
      opponent: opponentAbbr,
      value: nextGameProjection,
      hit: line > 0 ? nextGameProjection > line : false,
      result: 'PROJ',
      isHome: '',
    })
  }

  return (
    <div className="space-y-4">
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" style={{ fontSize: 12 }} />
            <YAxis stroke="hsl(var(--muted-foreground))" style={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }}
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null
                const data = payload[0].payload
                return (
                  <div className="bg-card border border-border rounded-lg p-3">
                    <p className="font-semibold mb-1">{data.isHome} {data.opponent}</p>
                    <p className="text-sm">{statType === 'threes' ? '3PM' : statType.toUpperCase()}: <span className="font-bold">{data.value}</span></p>
                    {line > 0 && <p className={`text-sm ${data.hit ? 'text-green-500' : 'text-red-500'}`}>{data.hit ? '✓ Over' : '✗ Under'} {line}</p>}
                  </div>
                )
              }}
            />
            {line > 0 && <ReferenceLine y={line} stroke="#ef4444" strokeDasharray="3 3" label={{ value: `Line: ${line.toFixed(1)}`, fill: '#ef4444', fontSize: 12, position: 'right' }} />}
            <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2}
              dot={(props: any) => {
                const { cx, cy, payload } = props
                const isProj = payload.result === 'PROJ'
                return <circle cx={cx} cy={cy} r={isProj ? 6 : 5} fill={isProj ? '#3b82f6' : (payload.hit ? '#22c55e' : '#ef4444')} stroke={isProj ? '#3b82f6' : (payload.hit ? '#22c55e' : '#ef4444')} strokeWidth={2} />
              }}
              activeDot={{ r: 7 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center justify-center gap-6 text-sm flex-wrap">
        {line > 0 && (
          <>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-green-500" /><span className="text-muted-foreground">Over</span></div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500" /><span className="text-muted-foreground">Under</span></div>
          </>
        )}
        {nextGameProjection && <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-blue-500" /><span className="text-muted-foreground">Projection</span></div>}
      </div>
      {filteredGames.length > 0 && (
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="p-3 rounded-lg bg-muted/30"><div className="text-xs text-muted-foreground mb-1">Average</div><div className="text-lg font-bold">{(chartData.reduce((sum, d) => sum + d.value, 0) / chartData.length).toFixed(1)}</div></div>
          {line > 0 && (
            <>
              <div className="p-3 rounded-lg bg-muted/30"><div className="text-xs text-muted-foreground mb-1">Hit Rate</div><div className="text-lg font-bold">{((chartData.filter(d => d.hit).length / chartData.length) * 100).toFixed(0)}%</div></div>
              <div className="p-3 rounded-lg bg-muted/30"><div className="text-xs text-muted-foreground mb-1">Record</div><div className="text-lg font-bold">{chartData.filter(d => d.hit).length}-{chartData.filter(d => !d.hit).length}</div></div>
            </>
          )}
        </div>
      )}
    </div>
  )
}