import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import type { Edge } from '@/api/types'

type BetResult = 'pending' | 'won' | 'lost' | 'push'
type ParlayStrategy = 'edge' | 'streak' | 'vegas'

interface ParlayRecommendation {
  id: string
  legs: Edge[]
  legCount: number
  strategy: ParlayStrategy
  combinedOdds: number
  impliedWinRate: number
  correlationScore: number
  expectedValue: number
}

interface TrackedParlay {
  id: string
  label: string
  stake: number
  toWin: number
  result: BetResult
}

const TRACKER_STORAGE_KEY = 'trackedParlays'
const BANKROLL_STORAGE_KEY = 'parlayBankroll'

function americanToDecimal(odds: number) {
  if (!odds) return 1.91
  return odds > 0 ? 1 + odds / 100 : 1 + 100 / Math.abs(odds)
}

function decimalToAmerican(decimal: number) {
  if (decimal <= 1) return -10000
  if (decimal >= 2) return Math.round((decimal - 1) * 100)
  return Math.round(-100 / (decimal - 1))
}

function getLegOdds(leg: Edge) {
  const rawOdds = leg.recommendation === 'OVER' ? leg.over_odds : leg.under_odds
  return rawOdds || -110
}

function correlationBetween(a: Edge, b: Edge) {
  let score = 0

  if (a.team_abbr === b.team_abbr) score += 0.4
  if (a.opp_abbr === b.opp_abbr && a.team_abbr === b.team_abbr) score += 0.2
  if ((a.stat_type === 'assists' && b.stat_type === 'points') || (a.stat_type === 'points' && b.stat_type === 'assists')) score += 0.3
  if ((a.stat_type === 'rebounds' && b.stat_type === 'points') || (a.stat_type === 'points' && b.stat_type === 'rebounds')) score -= 0.1

  return score
}

function makeParlayCombos(edges: Edge[], size: number, start = 0, current: Edge[] = [], combos: Edge[][] = []) {
  if (current.length === size) {
    combos.push([...current])
    return combos
  }

  for (let i = start; i < edges.length; i += 1) {
    const edge = edges[i]
    if (current.some((leg) => leg.player_id === edge.player_id)) continue

    current.push(edge)
    makeParlayCombos(edges, size, i + 1, current, combos)
    current.pop()
  }

  return combos
}

function buildRecommendation(legs: Edge[], strategy: ParlayStrategy): ParlayRecommendation {
  const decimalOdds = legs.reduce((total, leg) => total * americanToDecimal(getLegOdds(leg)), 1)
  const impliedWinRate = legs.reduce((total, leg) => {
    const winRate = leg.recommendation === 'OVER' ? leg.over_prob : leg.under_prob
    return total * (Math.max(winRate || 50, 1) / 100)
  }, 1)

  let correlationScore = 0
  for (let i = 0; i < legs.length; i += 1) {
    for (let j = i + 1; j < legs.length; j += 1) {
      correlationScore += correlationBetween(legs[i], legs[j])
    }
  }

  const expectedValue = impliedWinRate * (decimalOdds - 1) - (1 - impliedWinRate)

  return {
    id: `${strategy}-${legs.map((leg) => `${leg.player_id}-${leg.stat_type}`).join('-')}`,
    legs,
    legCount: legs.length,
    strategy,
    combinedOdds: decimalToAmerican(decimalOdds),
    impliedWinRate,
    correlationScore,
    expectedValue,
  }
}

function payout(stake: number, toWin: number, result: BetResult) {
  if (result === 'won') return toWin
  if (result === 'lost') return -stake
  return 0
}

function strategyLabel(strategy: ParlayStrategy) {
  if (strategy === 'edge') return 'Best Edge%'
  if (strategy === 'streak') return 'Best Streak'
  return 'Highest Vegas Odds'
}

export default function BetsPage() {
  const navigate = useNavigate()
  const { data: edges = [], isLoading } = useEdgeFinder('', '', 4)

  const [bankroll, setBankroll] = useState<number>(() => {
    const raw = localStorage.getItem(BANKROLL_STORAGE_KEY)
    const value = raw ? Number(raw) : 100
    return Number.isFinite(value) && value >= 0 ? value : 100
  })

  const [trackedParlays, setTrackedParlays] = useState<TrackedParlay[]>(() => {
    const raw = localStorage.getItem(TRACKER_STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  })

  const persistTracked = (next: TrackedParlay[]) => {
    setTrackedParlays(next)
    localStorage.setItem(TRACKER_STORAGE_KEY, JSON.stringify(next))
  }

  const saveBankroll = (value: number) => {
    const normalized = Number.isFinite(value) && value >= 0 ? Number(value.toFixed(2)) : 0
    setBankroll(normalized)
    localStorage.setItem(BANKROLL_STORAGE_KEY, String(normalized))
  }

  const suggestedUnitStake = useMemo(() => {
    if (bankroll <= 0) return 1
    return Math.max(1, Number((bankroll * 0.02).toFixed(2)))
  }, [bankroll])

  const candidateEdges = useMemo(
    () => edges
      .filter((edge) => edge.recommendation !== 'PASS')
      .sort((a, b) => ((b.expected_value || b.edge_pct) - (a.expected_value || a.edge_pct)))
      .slice(0, 16),
    [edges]
  )

  const parlaysByLegCount = useMemo(() => {
    const sizes = [2, 4, 6]
    const output: Record<number, ParlayRecommendation[]> = { 2: [], 4: [], 6: [] }

    sizes.forEach((size) => {
      if (candidateEdges.length < size) return

      const combos = makeParlayCombos(candidateEdges, size)
      if (!combos.length) return

      const recommendations = combos.map((legs) => buildRecommendation(legs, 'edge'))

      const byEdge = [...recommendations]
        .sort((a, b) => {
          const edgeA = a.legs.reduce((sum, leg) => sum + (leg.edge_pct || 0), 0)
          const edgeB = b.legs.reduce((sum, leg) => sum + (leg.edge_pct || 0), 0)
          return edgeB - edgeA
        })[0]

      const byStreak = [...recommendations]
        .sort((a, b) => {
          const streakA = a.legs.reduce((sum, leg) => sum + ((leg.streak?.hit_rate || 0) + (leg.streak?.current_streak || 0) * 5), 0)
          const streakB = b.legs.reduce((sum, leg) => sum + ((leg.streak?.hit_rate || 0) + (leg.streak?.current_streak || 0) * 5), 0)
          return streakB - streakA
        })[0]

      const byVegas = [...recommendations]
        .sort((a, b) => americanToDecimal(b.combinedOdds) - americanToDecimal(a.combinedOdds))[0]

      output[size] = [
        { ...byEdge, strategy: 'edge' },
        { ...byStreak, strategy: 'streak' },
        { ...byVegas, strategy: 'vegas' },
      ]
    })

    return output
  }, [candidateEdges])

  const strategy442 = useMemo(() => {
    const twoLeg = parlaysByLegCount[2]
    if (twoLeg.length < 2) return []

    const first = twoLeg[0]
    const second = twoLeg[1]
    const fourLegger = buildRecommendation([...first.legs, ...second.legs], 'edge')

    return [
      { label: '$4 - 2 Legger (Edge%)', stake: 4, parlay: first },
      { label: '$4 - 2 Legger (Streak)', stake: 4, parlay: second },
      { label: '$2 - Combined 4 Legger', stake: 2, parlay: fourLegger },
    ]
  }, [parlaysByLegCount])

  const addTrackedParlay = (label: string, stake: number, parlay: ParlayRecommendation) => {
    const decimal = americanToDecimal(parlay.combinedOdds)
    const toWin = Number((stake * (decimal - 1)).toFixed(2))
    persistTracked([
      {
        id: crypto.randomUUID(),
        label,
        stake,
        toWin,
        result: 'pending',
      },
      ...trackedParlays,
    ])
  }

  const updateResult = (id: string, result: BetResult) => {
    persistTracked(trackedParlays.map((bet) => (bet.id === id ? { ...bet, result } : bet)))
  }

  const bankrollSummary = useMemo(() => {
    const totalStaked = trackedParlays.reduce((sum, bet) => sum + bet.stake, 0)
    const pnl = trackedParlays.reduce((sum, bet) => sum + payout(bet.stake, bet.toWin, bet.result), 0)
    const currentBankroll = bankroll + pnl

    return {
      totalStaked,
      pnl,
      roi: totalStaked ? (pnl / totalStaked) * 100 : 0,
      currentBankroll,
    }
  }, [trackedParlays, bankroll])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Parlay Builder</h1>
        <p className="text-muted-foreground">3 picks per leg size: Edge%, Streak, and Highest Vegas Odds. Parlays avoid duplicate players.</p>
      </div>

      <div className="rounded-lg border border-border p-4 bg-card space-y-3">
        <label className="text-sm font-medium block">Starting Bankroll ($)</label>
        <input
          type="number"
          min="0"
          step="1"
          value={bankroll}
          onChange={(event) => saveBankroll(Number(event.target.value))}
          className="w-full md:w-72 px-3 py-2 rounded-md border border-border bg-background text-sm"
        />
        <p className="text-xs text-muted-foreground">Suggested 1-unit stake (2% bankroll): ${suggestedUnitStake.toFixed(2)}</p>
      </div>

      <div className="grid md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-border p-4 bg-card">
          <div className="text-xs text-muted-foreground">Current Bankroll</div>
          <div className="text-2xl font-bold">${bankrollSummary.currentBankroll.toFixed(2)}</div>
        </div>
        <div className="rounded-lg border border-border p-4 bg-card">
          <div className="text-xs text-muted-foreground">Total Staked</div>
          <div className="text-2xl font-bold">${bankrollSummary.totalStaked.toFixed(2)}</div>
        </div>
        <div className="rounded-lg border border-border p-4 bg-card">
          <div className="text-xs text-muted-foreground">Net P/L</div>
          <div className={`text-2xl font-bold ${bankrollSummary.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {bankrollSummary.pnl >= 0 ? '+' : ''}${bankrollSummary.pnl.toFixed(2)}
          </div>
        </div>
        <div className="rounded-lg border border-border p-4 bg-card">
          <div className="text-xs text-muted-foreground">ROI</div>
          <div className={`text-2xl font-bold ${bankrollSummary.roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {bankrollSummary.roi >= 0 ? '+' : ''}{bankrollSummary.roi.toFixed(1)}%
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-border p-6 text-muted-foreground">Building recommended parlays...</div>
      ) : (
        <div className="space-y-6">
          {[2, 4, 6].map((size) => (
            <section key={size} className="space-y-3">
              <h2 className="text-xl font-semibold">{size}-Leggers (3 Strategies)</h2>
              <div className="grid lg:grid-cols-3 gap-3">
                {(parlaysByLegCount[size] || []).map((parlay) => (
                  <div
                    key={parlay.id}
                    onClick={() => navigate(`/player/${parlay.legs[0].player_id}`)}
                    className="rounded-lg border border-border p-4 bg-card space-y-3 cursor-pointer hover:border-primary/60 transition-colors"
                  >
                    <div className="flex justify-between items-center">
                      <div className="font-semibold">{strategyLabel(parlay.strategy)}</div>
                      <div className="text-sm text-primary">{parlay.combinedOdds > 0 ? `+${parlay.combinedOdds}` : parlay.combinedOdds}</div>
                    </div>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {parlay.legs.map((leg) => (
                        <li key={`${parlay.id}-${leg.player_id}-${leg.stat_type}`}>{leg.player_name} {leg.recommendation} {leg.stat_type} ({leg.line})</li>
                      ))}
                    </ul>
                    <div className="text-xs text-muted-foreground">Corr: {parlay.correlationScore.toFixed(2)} | Est Win: {(parlay.impliedWinRate * 100).toFixed(1)}% | EV: {(parlay.expectedValue * 100).toFixed(1)}%</div>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        addTrackedParlay(`${size}-Legger ${strategyLabel(parlay.strategy)}`, suggestedUnitStake, parlay)
                      }}
                      className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium"
                    >
                      Track ({`$${suggestedUnitStake.toFixed(2)}`})
                    </button>
                    <p className="text-[11px] text-muted-foreground">Click card to open first player card.</p>
                  </div>
                ))}
              </div>
            </section>
          ))}

          <section className="space-y-3">
            <h2 className="text-xl font-semibold">Recommended 4/4/2 Strategy ($10)</h2>
            <div className="grid lg:grid-cols-3 gap-3">
              {strategy442.map((entry) => (
                <div key={entry.label} className="rounded-lg border border-border p-4 bg-card space-y-2">
                  <div className="font-semibold">{entry.label}</div>
                  <div className="text-sm text-primary">Odds: {entry.parlay.combinedOdds > 0 ? `+${entry.parlay.combinedOdds}` : entry.parlay.combinedOdds}</div>
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {entry.parlay.legs.map((leg) => (
                      <li key={`${entry.label}-${leg.player_id}-${leg.stat_type}`}>{leg.player_name} {leg.recommendation} {leg.stat_type}</li>
                    ))}
                  </ul>
                  <button onClick={() => addTrackedParlay(entry.label, entry.stake, entry.parlay)} className="w-full rounded-md border border-border py-2 text-sm hover:border-primary/70">
                    Add to tracker
                  </button>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Result Tracker</h2>
        <div className="space-y-2">
          {trackedParlays.length === 0 && <div className="rounded-lg border border-border p-4 text-muted-foreground">No tracked bets yet.</div>}
          {trackedParlays.map((bet) => (
            <div key={bet.id} className="rounded-lg border border-border p-3 bg-card flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-medium">{bet.label}</div>
                <div className="text-sm text-muted-foreground">Stake ${bet.stake.toFixed(2)} | To Win ${bet.toWin.toFixed(2)}</div>
              </div>
              <div className="flex items-center gap-2">
                {(['pending', 'won', 'lost', 'push'] as BetResult[]).map((result) => (
                  <button
                    key={result}
                    onClick={() => updateResult(bet.id, result)}
                    className={`px-3 py-1 rounded-md text-sm border ${bet.result === result ? 'border-primary text-primary' : 'border-border text-muted-foreground'}`}
                  >
                    {result}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
