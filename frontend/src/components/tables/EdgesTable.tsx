import { useNavigate } from 'react-router-dom'
import { Edge } from '@/api/types'
import { EdgeIndicator } from '@/components/projections/EdgeIndicator'
import { RecommendationBadge } from '@/components/projections/RecommendationBadge'
import { StatBadge } from '@/components/projections/StatBadge'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface EdgesTableProps {
  edges: Edge[]
  isLoading?: boolean
}

/**
 * Table displaying edges with sorting and click-to-view
 */
export function EdgesTable({ edges, isLoading }: EdgesTableProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center">
        <div className="text-muted-foreground">Loading edges...</div>
      </div>
    )
  }

  if (edges.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center">
        <div className="text-muted-foreground">No edges found</div>
        <p className="text-sm text-muted-foreground mt-2">
          Try adjusting your filters or check back later
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                Player
              </th>
              <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                Matchup
              </th>
              <th className="text-left p-4 text-sm font-medium text-muted-foreground">
                Stat
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                Line
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                Proj
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                Edge
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                No-Vig
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                Streak
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                Prob
              </th>
              <th className="text-center p-4 text-sm font-medium text-muted-foreground">
                Rec
              </th>
            </tr>
          </thead>
          <tbody>
            {edges.map((edge, index) => (
              <tr
                key={`${edge.player_id}-${edge.stat_type}-${index}`}
                onClick={() => navigate(`/player/${edge.player_id}`)}
                className="border-b border-border hover:bg-accent/50 cursor-pointer transition-colors"
              >
                <td className="p-4">
                  <div className="font-medium">{edge.player_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {edge.team_abbr} • {edge.position}
                  </div>
                </td>
                <td className="p-4">
                  <div className="text-sm">vs {edge.opp_abbr}</div>
                  {edge.matchup_grade && (
                    <div className="text-xs text-muted-foreground">
                      {edge.matchup_grade}
                    </div>
                  )}
                </td>
                <td className="p-4">
                  <StatBadge statType={edge.stat_type} />
                </td>
                <td className="p-4 text-center font-mono">
                  {edge.line.toFixed(1)}
                </td>
                <td className="p-4 text-center font-mono font-medium">
                  {edge.projected.toFixed(1)}
                </td>
                <td className="p-4 text-center">
                  <EdgeIndicator
                    edge={edge.edge_pct}
                    recommendation={edge.recommendation}
                  />
                </td>
                <td className="p-4 text-center">
                  {edge.recommendation === 'OVER' && edge.no_vig_fair_over !== undefined ? (
                    <div className="font-mono text-sm">
                      {(edge.no_vig_fair_over * 100).toFixed(1)}%
                    </div>
                  ) : edge.recommendation === 'UNDER' && edge.no_vig_fair_under !== undefined ? (
                    <div className="font-mono text-sm">
                      {(edge.no_vig_fair_under * 100).toFixed(1)}%
                    </div>
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </td>
                <td className="p-4 text-center">
                  {edge.streak && edge.streak.current_streak >= 3 ? (
                    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold ${
                      edge.streak.streak_type === 'hit'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {edge.streak.streak_type === 'hit' ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {edge.streak.current_streak}x
                    </div>
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </td>
                <td className="p-4 text-center font-mono text-sm">
                  {(() => {
                    const prob = edge.recommendation === 'OVER' ? edge.over_prob : edge.under_prob
                    // If prob > 1, it's already a percentage (e.g., 98.1)
                    // If prob <= 1, it's a decimal (e.g., 0.981) - multiply by 100
                    const displayProb = prob > 1 ? prob : prob * 100
                    return `${displayProb.toFixed(1)}%`
                  })()}
                </td>
                <td className="p-4 text-center">
                  <RecommendationBadge recommendation={edge.recommendation} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}