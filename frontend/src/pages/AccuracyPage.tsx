import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { TrendingUp, TrendingDown, Target, DollarSign, BarChart3, Percent } from 'lucide-react'
import { STAT_TYPES } from '@/lib/constants'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import { BetCard } from '@/components/projections/BetCard'
import type { Edge } from '@/api/types'

interface AccuracyData {
  stat_type: string
  days_back: number
  min_edge_filter: number | null
  sample_size: number
  overall: {
    win_rate: number
    wins: number
    losses: number
    pushes: number
    profit: number
    roi: number
  }
  error_metrics: {
    mae: number
    rmse: number
  }
  by_edge_size: {
    [key: string]: {
      win_rate: number
      sample_size: number
    }
  }
  by_recommendation: {
    over_win_rate: number
    under_win_rate: number
  }
}

const isAllowedAccuracyStat = (edge: Edge) => (
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

export default function AccuracyPage() {
  const [statType, setStatType] = useState('points')
  const [daysBack, setDaysBack] = useState(30)
  const [minEdge, setMinEdge] = useState<number | null>(null)
  const { data: edgesResponse } = useEdgeFinder(undefined, 'fanduel', 3.0, undefined)

  const edges: Edge[] = Array.isArray(edgesResponse) ? edgesResponse : []
  const eligibleEdges = edges.filter(isAllowedAccuracyStat)
  const topEdgeBets = [...eligibleEdges]
    .sort((a, b) => Math.abs(b.edge_pct) - Math.abs(a.edge_pct))
    .slice(0, 10)

  const topStreakyBets = [...eligibleEdges]
    .filter((edge) => edge.recommendation !== 'PASS' && getRecommendedSideStreak(edge) > 0)
    .sort((a, b) => getRecommendedSideStreak(b) - getRecommendedSideStreak(a))
    .slice(0, 10)

  const noVigTopBets = [...eligibleEdges]
    .filter((edge) => edge.recommendation !== 'PASS' && getRecommendedNoVigProbability(edge) > 0)
    .sort((a, b) => getRecommendedNoVigProbability(b) - getRecommendedNoVigProbability(a))
    .slice(0, 10)

  // Fetch accuracy data
  const { data: accuracy, isLoading, error } = useQuery<AccuracyData>({
    queryKey: ['accuracy', statType, daysBack, minEdge],
    queryFn: async () => {
      const params = new URLSearchParams({
        stat_type: statType,
        days_back: daysBack.toString(),
      })
      if (minEdge !== null) {
        params.append('min_edge', minEdge.toString())
      }
      const { data } = await apiClient.get(`/projections/accuracy?${params}`)
      return data
    },
  })

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-transparent to-primary/20 blur-2xl" />
        
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <Target className="w-8 h-8 text-primary" />
            <h1 className="text-5xl font-black tracking-tight">
              Model Accuracy
            </h1>
          </div>
          <p className="text-muted-foreground text-lg">
            Track historical projection performance and betting profitability
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-bold mb-4">Filters</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Stat Type */}
          <div>
            <label className="text-sm font-medium mb-2 block">Stat Type</label>
            <select
              value={statType}
              onChange={(e) => setStatType(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {Object.entries(STAT_TYPES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Time Period */}
          <div>
            <label className="text-sm font-medium mb-2 block">Time Period</label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value={1}>Yesterday</option>
              <option value={7}>Last 7 Days</option>
              <option value={14}>Last 14 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={60}>Last 60 Days</option>
              <option value={90}>Last 90 Days</option>
            </select>
          </div>

          {/* Min Edge Filter */}
          <div>
            <label className="text-sm font-medium mb-2 block">Min Edge Filter</label>
            <select
              value={minEdge === null ? 'all' : minEdge}
              onChange={(e) => setMinEdge(e.target.value === 'all' ? null : Number(e.target.value))}
              className="w-full px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="all">All Edges</option>
              <option value={3}>3%+ Edge</option>
              <option value={5}>5%+ Edge</option>
              <option value={8}>8%+ Edge</option>
              <option value={10}>10%+ Edge</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading accuracy data...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-red-500/50 bg-red-500/10 p-6">
          <div className="text-red-400 font-medium">Failed to load accuracy data</div>
          <div className="text-red-400/80 text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        </div>
      )}

      {/* No Data State */}
      {accuracy && accuracy.sample_size === 0 && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <Target className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-xl font-bold mb-2">No Graded Projections Yet</h3>
          <p className="text-muted-foreground">
            Projections are graded after games complete. Check back after game day!
          </p>
        </div>
      )}

      {/* Accuracy Data */}
      {accuracy && accuracy.sample_size > 0 && (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Win Rate */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-green-400" />
                </div>
                <div className="text-sm text-muted-foreground">Win Rate</div>
              </div>
              <div className="text-3xl font-bold text-green-400">
                {accuracy.overall.win_rate}%
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {accuracy.overall.wins}W - {accuracy.overall.losses}L
                {accuracy.overall.pushes > 0 && ` - ${accuracy.overall.pushes}P`}
              </div>
            </div>

            {/* Profit */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <DollarSign className="w-5 h-5 text-primary" />
                </div>
                <div className="text-sm text-muted-foreground">Total Profit</div>
              </div>
              <div className={`text-3xl font-bold ${
                accuracy.overall.profit >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {accuracy.overall.profit >= 0 ? '+' : ''}${accuracy.overall.profit.toFixed(2)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                At -110 odds, $100/bet
              </div>
            </div>

            {/* ROI */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Percent className="w-5 h-5 text-blue-400" />
                </div>
                <div className="text-sm text-muted-foreground">ROI</div>
              </div>
              <div className={`text-3xl font-bold ${
                accuracy.overall.roi >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {accuracy.overall.roi >= 0 ? '+' : ''}{accuracy.overall.roi}%
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Return on investment
              </div>
            </div>

            {/* Sample Size */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-orange-400" />
                </div>
                <div className="text-sm text-muted-foreground">Sample Size</div>
              </div>
              <div className="text-3xl font-bold">
                {accuracy.sample_size}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Graded projections
              </div>
            </div>
          </div>

          {/* Error Metrics */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5" />
              Prediction Accuracy
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <div className="text-sm text-muted-foreground mb-2">Mean Absolute Error (MAE)</div>
                <div className="text-2xl font-bold font-mono">
                  {accuracy.error_metrics.mae}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Average prediction error (lower is better)
                </p>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-2">Root Mean Squared Error (RMSE)</div>
                <div className="text-2xl font-bold font-mono">
                  {accuracy.error_metrics.rmse}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Penalizes larger errors more (lower is better)
                </p>
              </div>
            </div>
          </div>

          {/* Performance by Edge Size */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Performance by Edge Size
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(accuracy.by_edge_size).map(([bucket, stats]) => (
                <div key={bucket} className="rounded-lg border border-border bg-background p-4">
                  <div className="text-sm font-medium text-muted-foreground mb-2">
                    {bucket} Edge
                  </div>
                  <div className="text-2xl font-bold mb-1">
                    {stats.win_rate}%
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {stats.sample_size} bets
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full ${
                        stats.win_rate >= 55 ? 'bg-green-500' :
                        stats.win_rate >= 52.38 ? 'bg-yellow-500' :
                        'bg-red-500'
                      }`}
                      style={{ width: `${stats.win_rate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-4">
              💡 Need 52.38% win rate to break even at -110 odds
            </p>
          </div>

          {/* Performance by Bet Type */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-xl font-bold mb-4">Performance by Bet Type</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Over Bets */}
              <div className="rounded-lg border border-border bg-background p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center">
                    <TrendingUp className="w-6 h-6 text-green-400" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">OVER Bets</div>
                    <div className="text-2xl font-bold text-green-400">
                      {accuracy.by_recommendation.over_win_rate}%
                    </div>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-green-500"
                    style={{ width: `${accuracy.by_recommendation.over_win_rate}%` }}
                  />
                </div>
              </div>

              {/* Under Bets */}
              <div className="rounded-lg border border-border bg-background p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-lg bg-red-500/10 flex items-center justify-center">
                    <TrendingDown className="w-6 h-6 text-red-400" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">UNDER Bets</div>
                    <div className="text-2xl font-bold text-red-400">
                      {accuracy.by_recommendation.under_win_rate}%
                    </div>
                  </div>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-red-500"
                    style={{ width: `${accuracy.by_recommendation.under_win_rate}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Info Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-6">
              <h3 className="font-bold text-blue-400 mb-2">How Grading Works</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Projections saved when edge finder runs</li>
                <li>• Graded after games complete (next day)</li>
                <li>• Compared to actual player performance</li>
                <li>• Tracks win/loss for recommended bets</li>
                <li>• Calculates profit at -110 odds</li>
              </ul>
            </div>

            <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-6">
              <h3 className="font-bold text-green-400 mb-2">What's Good?</h3>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• <strong>Win Rate:</strong> 55%+ is excellent at -110</li>
                <li>• <strong>ROI:</strong> 5%+ is profitable long-term</li>
                <li>• <strong>MAE:</strong> Lower = more accurate predictions</li>
                <li>• <strong>Sample Size:</strong> 100+ bets for confidence</li>
                <li>• <strong>Consistency:</strong> All edge sizes profitable</li>
              </ul>
            </div>
          </div>

          {/* Today's Best Bet Tracking */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight">Today&apos;s Best 10 Edge Bets</h2>
            {topEdgeBets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {topEdgeBets.map((edge, index) => (
                  <BetCard key={`accuracy-top-edge-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No edge bets found today.
              </div>
            )}
          </section>

          <section className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight">Top 10 Streaky Bets</h2>
            {topStreakyBets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {topStreakyBets.map((edge, index) => (
                  <BetCard key={`accuracy-streak-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No streak-based bets found today.
              </div>
            )}
          </section>

          <section className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight">Today&apos;s No-Vig Odds Bets (Top 10)</h2>
            {noVigTopBets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                {noVigTopBets.map((edge, index) => (
                  <BetCard key={`accuracy-no-vig-${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No no-vig bet opportunities found today.
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
