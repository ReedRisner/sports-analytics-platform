import { MatchupContext } from '@/api/types'
import { Shield, TrendingUp, Users } from 'lucide-react'
import { cn } from '@/lib/utils'
import { GRADE_COLORS } from '@/lib/constants'

interface OpponentBreakdownProps {
  matchup?: MatchupContext
  statType: string
}

/**
 * Opponent matchup analysis
 */
export function OpponentBreakdown({ matchup, statType }: OpponentBreakdownProps) {
  if (!matchup) {
    return (
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Opponent Breakdown</h2>
        <p className="text-muted-foreground text-sm">
          No matchup data available
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card p-6 space-y-6">
      <h2 className="text-lg font-semibold">Opponent Breakdown</h2>

      {/* Opponent Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground mb-1">Opponent</div>
          <div className="text-3xl font-bold">{matchup.opp_name}</div>
          <div className="text-sm text-muted-foreground mt-1">
            {matchup.is_home ? 'Home' : 'Away'} game
          </div>
        </div>
        <div className={cn(
          'px-4 py-2 rounded-lg border font-semibold',
          GRADE_COLORS[matchup.matchup_grade as keyof typeof GRADE_COLORS] || 'bg-gray-500/20 text-gray-400 border-gray-500'
        )}>
          {matchup.matchup_grade}
        </div>
      </div>

      {/* Key Stats Grid */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-primary" />
            <span className="text-sm text-muted-foreground">Pace Factor</span>
          </div>
          <div className="text-2xl font-bold font-mono">{matchup.pace_factor.toFixed(2)}x</div>
          <div className="text-xs text-muted-foreground mt-1">
            {matchup.opp_pace.toFixed(1)} possessions/game
          </div>
        </div>

        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-primary" />
            <span className="text-sm text-muted-foreground">Matchup Factor</span>
          </div>
          <div className="text-2xl font-bold font-mono">{matchup.matchup_factor.toFixed(2)}x</div>
          {matchup.def_rank && (
            <div className="text-xs text-muted-foreground mt-1">
              #{matchup.def_rank} ranked defense
            </div>
          )}
        </div>
      </div>

      {/* Defensive Stats */}
      {matchup.defense && (
        <div className="pt-4 border-t border-border">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-4 h-4 text-primary" />
            <h3 className="font-semibold">Defensive Stats vs Position</h3>
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            {matchup.defense.pts_allowed !== undefined && (
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground mb-1">Points Allowed</div>
                <div className="text-xl font-bold">{matchup.defense.pts_allowed.toFixed(1)}</div>
                {matchup.defense.pts_rank && (
                  <div className="text-xs text-muted-foreground mt-1">
                    #{matchup.defense.pts_rank} in league
                  </div>
                )}
              </div>
            )}

            {matchup.defense.reb_allowed !== undefined && (
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground mb-1">Rebounds Allowed</div>
                <div className="text-xl font-bold">{matchup.defense.reb_allowed.toFixed(1)}</div>
                {matchup.defense.reb_rank && (
                  <div className="text-xs text-muted-foreground mt-1">
                    #{matchup.defense.reb_rank} in league
                  </div>
                )}
              </div>
            )}

            {matchup.defense.ast_allowed !== undefined && (
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground mb-1">Assists Allowed</div>
                <div className="text-xl font-bold">{matchup.defense.ast_allowed.toFixed(1)}</div>
                {matchup.defense.ast_rank && (
                  <div className="text-xs text-muted-foreground mt-1">
                    #{matchup.defense.ast_rank} in league
                  </div>
                )}
              </div>
            )}

            {matchup.allowed_avg !== undefined && (
              <div className="rounded-lg bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground mb-1">Avg {statType.toUpperCase()} Allowed</div>
                <div className="text-xl font-bold">{matchup.allowed_avg.toFixed(1)}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
