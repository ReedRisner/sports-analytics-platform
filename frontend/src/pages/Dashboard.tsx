import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import { BetCard } from '@/components/projections/BetCard'
import { TrendingUp } from 'lucide-react'
import type { Edge } from '@/api/types'

const isAllowedDashboardStat = (edge: Edge) => (
  edge.stat_type !== 'steals' && edge.stat_type !== 'blocks'
)

const getRecommendedNoVigProbability = (edge: Edge): number => {
  if (edge.recommendation === 'OVER') return edge.no_vig_fair_over ?? 0
  if (edge.recommendation === 'UNDER') return edge.no_vig_fair_under ?? 0
  return 0
}

const getRecommendedSideStreak = (edge: Edge): number => {
  if (!edge.streak) return 0

  if (edge.recommendation === 'OVER') {
    return edge.streak.streak_type === 'hit' ? edge.streak.current_streak : 0
  }

  if (edge.recommendation === 'UNDER') {
    return edge.streak.streak_type === 'miss' ? edge.streak.current_streak : 0
  }

  return 0
}

/**
 * Dashboard - Best Bets of the Day
 */
export default function Dashboard() {
  const { data: edgesResponse, isLoading, error } = useEdgeFinder(
    undefined,
    'fanduel',
    3.0,
    undefined
  )

  const edges: Edge[] = Array.isArray(edgesResponse)
    ? edgesResponse
    : []

  // Exclude blocks/steals only. Keep threes for bet cards.
  const eligibleEdges = edges.filter(isAllowedDashboardStat)

  const topBets = [...eligibleEdges]
    .sort((a, b) => Math.abs(b.edge_pct) - Math.abs(a.edge_pct))
    .slice(0, 10)

  const streakiestOverBets = [...eligibleEdges]
    .filter((edge) => edge.recommendation === 'OVER' && getRecommendedSideStreak(edge) > 0)
    .sort((a, b) => getRecommendedSideStreak(b) - getRecommendedSideStreak(a))
    .slice(0, 5)

  const streakiestUnderBets = [...eligibleEdges]
    .filter((edge) => edge.recommendation === 'UNDER' && getRecommendedSideStreak(edge) > 0)
    .sort((a, b) => getRecommendedSideStreak(b) - getRecommendedSideStreak(a))
    .slice(0, 5)

  const noVigTopBets = [...eligibleEdges]
    .filter((edge) => edge.recommendation !== 'PASS' && getRecommendedNoVigProbability(edge) > 0)
    .sort((a, b) => getRecommendedNoVigProbability(b) - getRecommendedNoVigProbability(a))
    .slice(0, 10)

  const totalBetsFound = eligibleEdges.length

  return (
    <div className="space-y-10 pb-12">
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-transparent to-primary/20 blur-2xl" />

        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-5xl font-black tracking-tight bg-gradient-to-r from-black via-black to-black/60 bg-clip-text text-transparent">
              Today&apos;s Best Bets
            </h1>
            <div className="text-right">
              <div className="text-sm text-muted-foreground font-medium">
                {new Date().toLocaleDateString('en-US', {
                  weekday: 'long'
                })}
              </div>
              <div className="text-2xl font-bold">
                {new Date().toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                })}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6 mt-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm text-muted-foreground">
                <span className="font-bold text-foreground">{totalBetsFound}</span> edges found
              </span>
            </div>
            {topBets.length > 0 && (
              <>
                <div className="h-4 w-px bg-border" />
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    Top edge: <span className="font-bold text-green-400">
                      +{Math.abs(topBets[0].edge_pct).toFixed(1)}%
                    </span>
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-muted-foreground">Finding the best bets...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/50 bg-red-500/10 p-8 text-center">
          <div className="text-red-400 font-semibold text-lg mb-2">Unable to load bets</div>
          <div className="text-red-400/80 text-sm">
            {error instanceof Error ? error.message : 'Unknown error occurred'}
          </div>
          <div className="text-red-400/60 text-sm mt-2">
            Make sure your backend is running at http://localhost:8000
          </div>
        </div>
      )}

      {!isLoading && !error && topBets.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Top Edge Bets</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
            {topBets.map((edge, index) => (
              <BetCard key={`top-edge-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
            ))}
          </div>
        </section>
      )}

      {!isLoading && !error && (
        <section className="space-y-6">
          <h2 className="text-2xl font-bold tracking-tight">Today&apos;s Streakiest Bets</h2>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-green-400">Top 5 OVER Streaks</h3>
            {streakiestOverBets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {streakiestOverBets.map((edge, index) => (
                  <BetCard key={`streak-over-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No active OVER streaks found today.
              </div>
            )}
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-red-400">Top 5 UNDER Streaks</h3>
            {streakiestUnderBets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {streakiestUnderBets.map((edge, index) => (
                  <BetCard key={`streak-under-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No active UNDER streaks found today.
              </div>
            )}
          </div>
        </section>
      )}

      {!isLoading && !error && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Today&apos;s No-Vig Odds Bets (Top 10)</h2>
          {noVigTopBets.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
              {noVigTopBets.map((edge, index) => (
                <BetCard key={`no-vig-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
              No no-vig bet opportunities found today.
            </div>
          )}
        </section>
      )}

      {!isLoading && !error && topBets.length === 0 && (
        <div className="rounded-xl border border-border bg-card/50 p-12 text-center">
          <div className="text-muted-foreground text-lg mb-2">No bets found today</div>
          <p className="text-sm text-muted-foreground">
            Check back later or adjust your filters
          </p>
        </div>
      )}
    </div>
  )
}
