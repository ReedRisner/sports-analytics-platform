import { GameLog } from '@/api/types'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface GameLogChartProps {
  games: GameLog[]
  statType: string
  line: number
}

/**
 * Game log chart showing recent performance vs the line
 */
export function GameLogChart({ games, statType, line }: GameLogChartProps) {
  // Map games to chart data
  const chartData = games.map((game) => {
    // Get the stat value based on stat type
    let value = 0
    switch (statType) {
      case 'points':
        value = game.points
        break
      case 'rebounds':
        value = game.rebounds
        break
      case 'assists':
        value = game.assists
        break
      case 'steals':
        value = game.steals
        break
      case 'blocks':
        value = game.blocks
        break
      case 'pra':
        value = game.pra
        break
      default:
        value = game.points
    }

    const hit = value > line

    return {
      date: new Date(game.date).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' }),
      opponent: game.opp_abbr,
      value,
      hit,
      result: game.result,
    }
  }).reverse() // Reverse to show oldest first (left to right)

  if (chartData.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No game data available
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis 
            dataKey="date" 
            stroke="hsl(var(--muted-foreground))"
            style={{ fontSize: 12 }}
          />
          <YAxis 
            stroke="hsl(var(--muted-foreground))"
            style={{ fontSize: 12 }}
          />

          {/* ✅ ONLY CHANGE: force solid tooltip background */}
          <Tooltip
            wrapperStyle={{ backgroundColor: '#0f172a' }} 
            contentStyle={{ 
              backgroundColor: '#0f172a',   // fully solid
              border: '1px solid #1e293b',
              borderRadius: '8px',
              opacity: 1,
            }}
            labelStyle={{ color: '#ffffff' }}
            itemStyle={{ color: '#ffffff' }}
          />
          
          {/* Reference line for the betting line */}
          <ReferenceLine 
            y={line} 
            stroke="#ef4444" 
            strokeDasharray="3 3"
            label={{ 
              value: `Line: ${line.toFixed(1)}`, 
              fill: '#ef4444',
              fontSize: 12,
              position: 'right'
            }}
          />
          
          {/* Main line */}
          <Line 
            type="monotone" 
            dataKey="value" 
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={(props: any) => {
              const { cx, cy, payload } = props
              return (
                <circle
                  cx={cx}
                  cy={cy}
                  r={5}
                  fill={payload.hit ? '#22c55e' : '#ef4444'}
                  stroke={payload.hit ? '#22c55e' : '#ef4444'}
                  strokeWidth={2}
                />
              )
            }}
            activeDot={{ r: 7 }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-muted-foreground">Hit (Over Line)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-muted-foreground">Miss (Under Line)</span>
        </div>
      </div>
    </div>
  )
}
