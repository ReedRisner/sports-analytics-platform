import { Projection } from '@/api/types'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { STAT_TYPES } from '@/lib/constants'

interface ProjectionCardProps {
  projection?: Projection
  odds?: any
  statType: string
}

/**
 * Projection card showing our projection vs the line
 */
export function ProjectionCard({ projection, odds, statType }: ProjectionCardProps) {
  if (!projection || !odds) {
    return (
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Projection</h2>
        <p className="text-muted-foreground text-sm">
          No projection available for {STAT_TYPES[statType as keyof typeof STAT_TYPES] || statType}
        </p>
      </div>
    )
  }

  const isOver = projection.recommendation === 'OVER'
  const isPass = projection.recommendation === 'PASS'
  
  return (
    <div className="rounded-xl border border-border bg-card p-6 space-y-6">
      <h2 className="text-lg font-semibold">Projection</h2>

      {/* Projected Value */}
      <div>
        <div className="text-sm text-muted-foreground mb-1">Our Projection</div>
        <div className="text-5xl font-bold font-mono text-primary">
          {projection.projected.toFixed(1)}
        </div>
      </div>

      {/* Line */}
      <div className="pt-4 border-t border-border">
        <div className="text-sm text-muted-foreground mb-2">FanDuel Line</div>
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border border-border p-3">
            <div className="text-xs text-muted-foreground mb-1">OVER</div>
            <div className="text-xl font-bold font-mono">{odds.line.toFixed(1)}</div>
            <div className="text-xs text-muted-foreground mt-1">{odds.over_odds > 0 ? '+' : ''}{odds.over_odds}</div>
          </div>
          <div className="rounded-lg border border-border p-3">
            <div className="text-xs text-muted-foreground mb-1">UNDER</div>
            <div className="text-xl font-bold font-mono">{odds.line.toFixed(1)}</div>
            <div className="text-xs text-muted-foreground mt-1">{odds.under_odds > 0 ? '+' : ''}{odds.under_odds}</div>
          </div>
        </div>
      </div>

      {/* Edge & Recommendation */}
      <div className="pt-4 border-t border-border">
        <div
          className={cn(
            'rounded-lg p-4 border',
            isPass && 'bg-gray-500/10 border-gray-500/50',
            !isPass && isOver && 'bg-green-500/10 border-green-500/50',
            !isPass && !isOver && 'bg-red-500/10 border-red-500/50'
          )}
        >
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Recommendation</div>
              <div
                className={cn(
                  'text-2xl font-bold',
                  isPass && 'text-gray-400',
                  !isPass && isOver && 'text-green-400',
                  !isPass && !isOver && 'text-red-400'
                )}
              >
                {projection.recommendation}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted-foreground mb-1">Edge</div>
              <div
                className={cn(
                  'text-2xl font-bold font-mono',
                  isPass && 'text-gray-400',
                  !isPass && isOver && 'text-green-400',
                  !isPass && !isOver && 'text-red-400'
                )}
              >
                {projection.edge_pct > 0 ? '+' : ''}{projection.edge_pct.toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Win Probability */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Win Probability</span>
            <span className="font-mono font-semibold">
              {isOver 
                ? `${(projection.over_prob * 100).toFixed(1)}%`
                : `${(projection.under_prob * 100).toFixed(1)}%`
              }
            </span>
          </div>
        </div>
      </div>

      {/* Range */}
      <div className="pt-4 border-t border-border">
        <div className="text-sm text-muted-foreground mb-3">Projected Range</div>
        <div className="flex items-center justify-between">
          <div className="text-center">
            <div className="text-xs text-muted-foreground mb-1">Floor</div>
            <div className="text-lg font-bold font-mono">{projection.floor.toFixed(1)}</div>
          </div>
          <div className="flex-1 mx-4">
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full"
                style={{
                  marginLeft: `${((projection.projected - projection.floor) / (projection.ceiling - projection.floor)) * 50}%`,
                  width: '4px',
                }}
              />
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground mb-1">Ceiling</div>
            <div className="text-lg font-bold font-mono">{projection.ceiling.toFixed(1)}</div>
          </div>
        </div>
      </div>

      {/* Confidence */}
      {projection.confidence && (
        <div className="pt-4 border-t border-border">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Confidence</span>
            <span className="font-semibold">{(projection.confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
      )}
    </div>
  )
}
