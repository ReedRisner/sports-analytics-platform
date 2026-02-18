import { useNavigate } from 'react-router-dom'
import { Edge } from '@/api/types'
import { Star } from 'lucide-react'
import { cn } from '@/lib/utils'
import { STAT_COLORS } from '@/lib/constants'

interface BetCardProps {
  edge: Edge
  rank: number
}

/**
 * Calculate star rating (1-5 stars) based on edge percentage
 */
function getStarRating(edgePct: number): number {
  const absEdge = Math.abs(edgePct)
  if (absEdge >= 18) return 5
  if (absEdge >= 12) return 4
  if (absEdge >= 8) return 3
  if (absEdge >= 5) return 2
  return 1
}

/**
 * Individual bet card component
 */
export function BetCard({ edge, rank }: BetCardProps) {
  const navigate = useNavigate()
  const stars = getStarRating(edge.edge_pct)
  const isOver = edge.recommendation === 'OVER'
  
  const statColor = STAT_COLORS[edge.stat_type.toLowerCase()] || 'text-foreground'

  // Backend returns probabilities as percentages already (e.g., 93.80 not 0.9380)
  // If value is < 1, it's a decimal, multiply by 100. If >= 1, it's already a percentage
  const winProbability = isOver ? edge.over_prob : edge.under_prob
  const winProbPct = winProbability < 1 
    ? (winProbability * 100).toFixed(1) 
    : winProbability.toFixed(1)

  return (
    <div
      onClick={() => navigate(`/player/${edge.player_id}`)}
      className="group relative rounded-xl border border-border bg-gradient-to-br from-card to-card/50 p-6 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 transition-all duration-300 cursor-pointer overflow-hidden"
    >
      {/* Rank Badge */}
      <div className="absolute top-3 left-3 w-8 h-8 rounded-full bg-primary/20 border border-primary/50 flex items-center justify-center">
        <span className="text-xs font-bold text-primary">#{rank}</span>
      </div>

      {/* Star Rating */}
      <div className="absolute top-3 right-3 flex gap-0.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star
            key={i}
            className={cn(
              'w-3.5 h-3.5',
              i < stars
                ? 'fill-yellow-400 text-yellow-400'
                : 'fill-gray-700 text-gray-700'
            )}
          />
        ))}
      </div>

      {/* Player Info */}
      <div className="mt-8 mb-4">
        <h3 className="text-xl font-bold mb-1 group-hover:text-primary transition-colors">
          {edge.player_name}
        </h3>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="font-medium">{edge.team_abbr}</span>
          <span>•</span>
          <span>{edge.position}</span>
          <span>•</span>
          <span>vs {edge.opp_abbr}</span>
        </div>
      </div>

      {/* Stat Type */}
      <div className="mb-4">
        <div className={cn('inline-flex items-center px-3 py-1.5 rounded-lg bg-background/50 border border-border', statColor)}>
          <span className="text-sm font-semibold uppercase tracking-wide">
            {edge.stat_type}
          </span>
        </div>
      </div>

      {/* Line & Projection */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Line</div>
          <div className="text-2xl font-bold font-mono">{edge.line.toFixed(1)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Projection</div>
          <div className="text-2xl font-bold font-mono text-primary">
            {edge.projected.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Recommendation Banner */}
      <div
        className={cn(
          'rounded-lg p-3 mb-3',
          isOver
            ? 'bg-green-500/20 border border-green-500/50'
            : 'bg-red-500/20 border border-red-500/50'
        )}
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-muted-foreground mb-0.5">
              Recommended
            </div>
            <div
              className={cn(
                'text-lg font-bold',
                isOver ? 'text-green-400' : 'text-red-400'
              )}
            >
              {edge.recommendation}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs font-medium text-muted-foreground mb-0.5">
              Edge
            </div>
            <div
              className={cn(
                'text-lg font-bold font-mono',
                isOver ? 'text-green-400' : 'text-red-400'
              )}
            >
              {edge.edge_pct > 0 ? '+' : ''}{edge.edge_pct.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Win Probability */}
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-muted-foreground">Win Probability</span>
        <span className="font-mono font-semibold">
          {winProbPct}%
        </span>
      </div>

      {/* Matchup Grade */}
      {edge.matchup_grade && (
        <div className="pt-2 border-t border-border/50">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Matchup</span>
            <span
              className={cn(
                'px-2 py-0.5 rounded font-medium',
                edge.matchup_grade === 'Elite' && 'bg-green-500/20 text-green-400',
                edge.matchup_grade === 'Good' && 'bg-blue-500/20 text-blue-400',
                edge.matchup_grade === 'Neutral' && 'bg-gray-500/20 text-gray-400',
                edge.matchup_grade === 'Tough' && 'bg-orange-500/20 text-orange-400',
                edge.matchup_grade === 'Lockdown' && 'bg-red-500/20 text-red-400'
              )}
            >
              {edge.matchup_grade}
            </span>
          </div>
        </div>
      )}

      {/* Hover Effect Overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/0 to-primary/0 group-hover:from-primary/5 group-hover:to-primary/10 transition-all duration-300 pointer-events-none rounded-xl" />
    </div>
  )
}