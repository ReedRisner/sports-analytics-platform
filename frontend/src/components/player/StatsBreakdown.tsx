import { Projection, GameLog } from '@/api/types'
import { TrendingUp, Calendar, Home, Users } from 'lucide-react'

interface StatsBreakdownProps {
  projection?: Projection
  gameLog?: GameLog[]
  statType: string
}

/**
 * Stats breakdown showing averages and contextual factors
 */
export function StatsBreakdown({ projection, gameLog, statType }: StatsBreakdownProps) {
  if (!projection) {
    return null
  }

  // Calculate home/away splits if we have game log
  const homeSplits = gameLog?.filter(g => g.home_away === 'home')
  const awaySplits = gameLog?.filter(g => g.home_away === 'away')
  
  const getStatValue = (game: GameLog) => {
    switch (statType) {
      case 'points': return game.points
      case 'rebounds': return game.rebounds
      case 'assists': return game.assists
      case 'steals': return game.steals
      case 'blocks': return game.blocks
      case 'pra': return game.pra
      default: return 0
    }
  }

  const homeAvg = homeSplits && homeSplits.length > 0
    ? homeSplits.reduce((sum, g) => sum + getStatValue(g), 0) / homeSplits.length
    : null

  const awayAvg = awaySplits && awaySplits.length > 0
    ? awaySplits.reduce((sum, g) => sum + getStatValue(g), 0) / awaySplits.length
    : null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Averages Card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-semibold">Averages</h3>
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
        </div>
      </div>

      {/* Contextual Factors Card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Calendar className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-semibold">Context</h3>
        </div>

        <div className="space-y-3">
          {/* Home/Away Split */}
          {homeAvg !== null && awayAvg !== null && (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Home className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Home Average</span>
                </div>
                <span className="text-lg font-bold font-mono">{homeAvg.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Away Average</span>
                </div>
                <span className="text-lg font-bold font-mono">{awayAvg.toFixed(1)}</span>
              </div>
              <div className="pt-3 border-t border-border flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Home/Away Factor</span>
                <span className="text-lg font-bold font-mono">
                  {(homeAvg / awayAvg).toFixed(2)}x
                </span>
              </div>
            </>
          )}

          {/* Adjustments */}
          {projection.adjustments && (
            <>
              <div className="pt-3 border-t border-border">
                <div className="text-xs text-muted-foreground mb-2">Applied Adjustments</div>
                <div className="space-y-2">
                  {projection.adjustments.is_back_to_back && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Back-to-back</span>
                      <span className="text-orange-400">Yes</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Days Rest</span>
                    <span>{projection.adjustments.days_rest || 0}</span>
                  </div>
                  {projection.adjustments.home_factor !== 1 && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Home Factor</span>
                      <span>{projection.adjustments.home_factor.toFixed(2)}x</span>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
