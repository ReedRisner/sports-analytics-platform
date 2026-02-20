import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { TrendingUp, TrendingDown, Target, DollarSign, BarChart3, Percent } from 'lucide-react'
import { STAT_TYPES } from '@/lib/constants'

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
  top_edge_bets?: TrackedBet[]
  top_streaky_bets?: TrackedBet[]
  top_no_vig_bets?: TrackedBet[]
}

interface TrackedBet {
  player_id: number
  player_name: string
  team_abbr: string
  game_date: string
  stat_type: string
  recommendation: 'OVER' | 'UNDER' | 'PASS' | string
  bet_result: 'win' | 'loss' | 'push' | string
  line: number | null
  projected: number
  actual: number
  edge_pct: number
  no_vig_prob?: number | null
  streak_count?: number
  streak_type?: string
}

interface BetSummary {
  total: number
  wins: number
  losses: number
  pushes: number
  winRate: number
}

export default function AccuracyPage() {
  const [statType, setStatType] = useState('points')
  const [daysBack, setDaysBack] = useState(30)
  const [minEdge, setMinEdge] = useState<number | null>(null)
  const [showEdgeDetails, setShowEdgeDetails] = useState(false)
  const [showStreakDetails, setShowStreakDetails] = useState(false)

  const sectionLabel = daysBack === 1 ? 'Yesterday' : `Last ${daysBack} Days`
  const summarizeTrackedBets = (bets: TrackedBet[]): BetSummary => {
    const wins = bets.filter((bet) => bet.bet_result === 'win').length
    const losses = bets.filter((bet) => bet.bet_result === 'loss').length
    const pushes = bets.filter((bet) => bet.bet_result === 'push').length
    const graded = wins + losses
    const winRate = graded > 0 ? (wins / graded) * 100 : 0

    return {
      total: bets.length,
      wins,
      losses,
      pushes,
      winRate,
    }
  }

  const renderTrackedBets = (bets: TrackedBet[], showStreak = false) => (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-muted-foreground">
          <tr>
            <th className="p-3 text-left">Player</th>
            <th className="p-3 text-left">Bet</th>
            <th className="p-3 text-left">Edge</th>
            <th className="p-3 text-left">Proj / Line / Actual</th>
            {showStreak && <th className="p-3 text-left">Streak</th>}
            <th className="p-3 text-left">Result</th>
            <th className="p-3 text-left">Date</th>
          </tr>
        </thead>
        <tbody>
          {bets.map((bet, index) => (
            <tr key={`${bet.player_id}-${bet.stat_type}-${bet.game_date}-${index}`} className="border-t border-border">
              <td className="p-3 font-medium">
                {bet.player_name} <span className="text-muted-foreground">({bet.team_abbr})</span>
              </td>
              <td className="p-3">
                {bet.recommendation} {bet.stat_type}
              </td>
              <td className="p-3 font-mono">
                {bet.edge_pct > 0 ? '+' : ''}
                {bet.edge_pct.toFixed(1)}%
              </td>
              <td className="p-3 font-mono">
                {bet.projected.toFixed(1)} / {bet.line?.toFixed(1) ?? '-'} / {bet.actual.toFixed(1)}
              </td>
              {showStreak && <td className="p-3">{bet.streak_count ? `${bet.streak_count}x ${bet.streak_type}` : '-'}</td>}
              <td className={`p-3 font-semibold uppercase ${getResultColor(bet.bet_result)}`}>{bet.bet_result}</td>
              <td className="p-3 text-muted-foreground">{bet.game_date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const summarizeTrackedBets = (bets: TrackedBet[]): BetSummary => {
    const wins = bets.filter((bet) => bet.bet_result === 'win').length
    const losses = bets.filter((bet) => bet.bet_result === 'loss').length
    const pushes = bets.filter((bet) => bet.bet_result === 'push').length
    const graded = wins + losses
    const winRate = graded > 0 ? (wins / graded) * 100 : 0

    return {
      total: bets.length,
      wins,
      losses,
      pushes,
      winRate,
    }
  }

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

  const accuracyTopEdgeBets = accuracy?.top_edge_bets ?? []
  const accuracyTopStreakyBets = accuracy?.top_streaky_bets ?? []
  const accuracyNoVigTopBets = accuracy?.top_no_vig_bets ?? []
  const topEdgeSummary = summarizeTrackedBets(accuracyTopEdgeBets)
  const topStreakSummary = summarizeTrackedBets(accuracyTopStreakyBets)
  const topNoVigSummary = summarizeTrackedBets(accuracyNoVigTopBets)

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-transparent to-primary/20 blur-2xl" />

        <div className="relative">
          <div className="mb-2 flex items-center gap-3">
            <Target className="h-8 w-8 text-primary" />
            <h1 className="text-5xl font-black tracking-tight">Model Accuracy</h1>
          </div>
          <p className="text-lg text-muted-foreground">Track historical projection performance and betting profitability</p>
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="mb-4 text-lg font-bold">Filters</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* Stat Type */}
          <div>
            <label className="mb-2 block text-sm font-medium">Stat Type</label>
            <select
              value={statType}
              onChange={(e) => setStatType(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
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
            <label className="mb-2 block text-sm font-medium">Time Period</label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="w-full rounded-md border border-border bg-background px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
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
            <label className="mb-2 block text-sm font-medium">Min Edge Filter</label>
            <select
              value={minEdge === null ? 'all' : minEdge}
              onChange={(e) => setMinEdge(e.target.value === 'all' ? null : Number(e.target.value))}
              className="w-full rounded-md border border-border bg-background px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
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
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-muted-foreground">Loading accuracy data...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-red-500/50 bg-red-500/10 p-6">
          <div className="font-medium text-red-400">Failed to load accuracy data</div>
          <div className="mt-1 text-sm text-red-400/80">{error instanceof Error ? error.message : 'Unknown error'}</div>
        </div>
      )}

      {/* No Data State */}
      {accuracy && accuracy.sample_size === 0 && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <Target className="mx-auto mb-4 h-16 w-16 text-muted-foreground" />
          <h3 className="mb-2 text-xl font-bold">No Graded Projections Yet</h3>
          <p className="text-muted-foreground">Projections are graded after games complete. Check back after game day!</p>
        </div>
      )}

      {/* Accuracy Data */}
      {accuracy && accuracy.sample_size > 0 && (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            {/* Win Rate */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="mb-2 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10">
                  <TrendingUp className="h-5 w-5 text-green-400" />
                </div>
                <div className="text-sm text-muted-foreground">Win Rate</div>
              </div>
              <div className="text-3xl font-bold text-green-400">{accuracy.overall.win_rate}%</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {accuracy.overall.wins}W - {accuracy.overall.losses}L
                {accuracy.overall.pushes > 0 && ` - ${accuracy.overall.pushes}P`}
              </div>
            </div>

            {/* Profit */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="mb-2 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <DollarSign className="h-5 w-5 text-primary" />
                </div>
                <div className="text-sm text-muted-foreground">Total Profit</div>
              </div>
              <div className={`text-3xl font-bold ${accuracy.overall.profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {accuracy.overall.profit >= 0 ? '+' : ''}${accuracy.overall.profit.toFixed(2)}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">At -110 odds, $100/bet</div>
            </div>

            {/* ROI */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="mb-2 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                  <Percent className="h-5 w-5 text-blue-400" />
                </div>
                <div className="text-sm text-muted-foreground">ROI</div>
              </div>
              <div className={`text-3xl font-bold ${accuracy.overall.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {accuracy.overall.roi >= 0 ? '+' : ''}
                {accuracy.overall.roi}%
              </div>
              <div className="mt-1 text-xs text-muted-foreground">Return on investment</div>
            </div>

            {/* Sample Size */}
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="mb-2 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500/10">
                  <BarChart3 className="h-5 w-5 text-orange-400" />
                </div>
                <div className="text-sm text-muted-foreground">Sample Size</div>
              </div>
              <div className="text-3xl font-bold">{accuracy.sample_size}</div>
              <div className="mt-1 text-xs text-muted-foreground">Graded projections</div>
            </div>
          </div>

          {/* Error Metrics */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-bold">
              <Target className="h-5 w-5" />
              Prediction Accuracy
            </h2>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <div className="mb-2 text-sm text-muted-foreground">Mean Absolute Error (MAE)</div>
                <div className="font-mono text-2xl font-bold">{accuracy.error_metrics.mae}</div>
                <p className="mt-1 text-xs text-muted-foreground">Average prediction error (lower is better)</p>
              </div>
              <div>
                <div className="mb-2 text-sm text-muted-foreground">Root Mean Squared Error (RMSE)</div>
                <div className="font-mono text-2xl font-bold">{accuracy.error_metrics.rmse}</div>
                <p className="mt-1 text-xs text-muted-foreground">Penalizes larger errors more (lower is better)</p>
              </div>
            </div>
          </div>

          {/* Performance by Edge Size */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="mb-4 flex items-center gap-2 text-xl font-bold">
              <TrendingUp className="h-5 w-5" />
              Performance by Edge Size
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {Object.entries(accuracy.by_edge_size).map(([bucket, stats]) => (
                <div key={bucket} className="rounded-lg border border-border bg-background p-4">
                  <div className="mb-2 text-sm font-medium text-muted-foreground">{bucket} Edge</div>
                  <div className="mb-1 text-2xl font-bold">{stats.win_rate}%</div>
                  <div className="text-xs text-muted-foreground">{stats.sample_size} bets</div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full ${stats.win_rate >= 55 ? 'bg-green-500' : stats.win_rate >= 52.38 ? 'bg-yellow-500' : 'bg-red-500'}`}
                      style={{ width: `${stats.win_rate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-muted-foreground">💡 Need 52.38% win rate to break even at -110 odds</p>
          </div>

          {/* Performance by Bet Type */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="mb-4 text-xl font-bold">Performance by Bet Type</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {/* Over Bets */}
              <div className="rounded-lg border border-border bg-background p-6">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-500/10">
                    <TrendingUp className="h-6 w-6 text-green-400" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">OVER Bets</div>
                    <div className="text-2xl font-bold text-green-400">{accuracy.by_recommendation.over_win_rate}%</div>
                  </div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-green-500" style={{ width: `${accuracy.by_recommendation.over_win_rate}%` }} />
                </div>
              </div>

              {/* Under Bets */}
              <div className="rounded-lg border border-border bg-background p-6">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-red-500/10">
                    <TrendingDown className="h-6 w-6 text-red-400" />
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">UNDER Bets</div>
                    <div className="text-2xl font-bold text-red-400">{accuracy.by_recommendation.under_win_rate}%</div>
                  </div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-red-500" style={{ width: `${accuracy.by_recommendation.under_win_rate}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Info Cards */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-6">
              <h3 className="mb-2 font-bold text-blue-400">How Grading Works</h3>
              <ul className="space-y-1 text-sm text-muted-foreground">
                <li>• Projections saved when edge finder runs</li>
                <li>• Graded after games complete (next day)</li>
                <li>• Compared to actual player performance</li>
                <li>• Tracks win/loss for recommended bets</li>
                <li>• Calculates profit at -110 odds</li>
              </ul>
            </div>

            <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-6">
              <h3 className="mb-2 font-bold text-green-400">What's Good?</h3>
              <ul className="space-y-1 text-sm text-muted-foreground">
                <li>
                  • <strong>Win Rate:</strong> 55%+ is excellent at -110
                </li>
                <li>
                  • <strong>ROI:</strong> 5%+ is profitable long-term
                </li>
                <li>
                  • <strong>MAE:</strong> Lower = more accurate predictions
                </li>
                <li>
                  • <strong>Sample Size:</strong> 100+ bets for confidence
                </li>
                <li>
                  • <strong>Consistency:</strong> All edge sizes profitable
                </li>
              </ul>
            </div>
          </div>

          {/* Today's Best Bet Tracking */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight">Best 10 Edge Bets ({sectionLabel})</h2>
            {accuracyTopEdgeBets.length > 0 ? (
              <div
                className="cursor-pointer rounded-xl border border-border bg-card p-6 transition-colors hover:bg-muted/30"
                onClick={() => setShowEdgeDetails((current) => !current)}
              >
                <div className="text-sm text-muted-foreground">Winning Percentage</div>
                <div className="mt-2 text-4xl font-black text-green-400">{topEdgeSummary.winRate.toFixed(1)}%</div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {topEdgeSummary.wins} of {topEdgeSummary.wins + topEdgeSummary.losses} bets were right
                  {topEdgeSummary.pushes > 0 && ` (${topEdgeSummary.pushes} pushes)`}
                </div>
                <div className="mt-2 text-xs text-primary">{showEdgeDetails ? 'Hide details' : 'Click to show player details'}</div>
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No graded edge bets found for this filter.
              </div>
            )}
            {showEdgeDetails && accuracyTopEdgeBets.length > 0 && renderTrackedBets(accuracyTopEdgeBets)}
          </section>

          <section className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight">Top 10 Streaky Bets ({sectionLabel})</h2>
            {accuracyTopStreakyBets.length > 0 ? (
              <div
                className="cursor-pointer rounded-xl border border-border bg-card p-6 transition-colors hover:bg-muted/30"
                onClick={() => setShowStreakDetails((current) => !current)}
              >
                <div className="text-sm text-muted-foreground">Winning Percentage</div>
                <div className="mt-2 text-4xl font-black text-green-400">{topStreakSummary.winRate.toFixed(1)}%</div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {topStreakSummary.wins} of {topStreakSummary.wins + topStreakSummary.losses} bets were right
                  {topStreakSummary.pushes > 0 && ` (${topStreakSummary.pushes} pushes)`}
                </div>
                <div className="mt-2 text-xs text-primary">{showStreakDetails ? 'Hide details' : 'Click to show player details'}</div>
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No streak-based graded bets found for this filter.
              </div>
            )}
            {showStreakDetails && accuracyTopStreakyBets.length > 0 && renderTrackedBets(accuracyTopStreakyBets, true)}
          </section>

          <section className="space-y-4">
            <h2 className="text-2xl font-bold tracking-tight">No-Vig Odds Bets (Top 10, {sectionLabel})</h2>
            {accuracyNoVigTopBets.length > 0 ? (
              <div className="rounded-xl border border-border bg-card p-6">
                <div className="text-sm text-muted-foreground">Winning Percentage</div>
                <div className="mt-2 text-4xl font-black text-green-400">{topNoVigSummary.winRate.toFixed(1)}%</div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {topNoVigSummary.wins} of {topNoVigSummary.wins + topNoVigSummary.losses} bets were right
                  {topNoVigSummary.pushes > 0 && ` (${topNoVigSummary.pushes} pushes)`}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-border bg-card/50 p-6 text-sm text-muted-foreground">
                No no-vig graded bets found for this filter.
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
