import { useMemo, useState } from 'react'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import type { Edge } from '@/api/types'

type BetResult = 'pending' | 'won' | 'lost' | 'push'

interface ParlayRecommendation {
  id: string
  legs: Edge[]
  legCount: number
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

const STORAGE_KEY = 'trackedParlays'

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
  const isOver = leg.recommendation === 'OVER'
  const rawOdds = isOver ? leg.over_odds : leg.under_odds
  return rawOdds || -110
}

function correlationBetween(a: Edge, b: Edge) {
  let score = 0

  if (a.team_abbr === b.team_abbr) score += 0.4
  if (a.opp_abbr === b.opp_abbr && a.team_abbr === b.team_abbr) score += 0.2
  if (a.stat_type === b.stat_type) score += 0.1
  if ((a.stat_type === 'assists' && b.stat_type === 'points') || (a.stat_type === 'points' && b.stat_type === 'assists')) score += 0.3
  if ((a.stat_type === 'rebounds' && b.stat_type === 'points') || (a.stat_type === 'points' && b.stat_type === 'rebounds')) score -= 0.1

  return score
}

function makeParlayCombo(edges: Edge[], size: number, seen = new Set<string>(), start = 0, current: Edge[] = [], combos: Edge[][] = []) {
  if (current.length === size) {
    const id = current.map((e) => `${e.player_id}-${e.stat_type}-${e.recommendation}`).join('|')
    if (!seen.has(id)) {
      seen.add(id)
      combos.push([...current])
    }
    return combos
  }

  for (let i = start; i < edges.length; i += 1) {
    current.push(edges[i])
    makeParlayCombo(edges, size, seen, i + 1, current, combos)
    current.pop()
  }

  return combos
}

function toRecommendation(legs: Edge[]): ParlayRecommendation {
  const decimalOdds = legs.reduce((product, leg) => product * americanToDecimal(getLegOdds(leg)), 1)
  const impliedWinRate = legs.reduce((product, leg) => {
    const legWinProb = leg.recommendation === 'OVER' ? leg.over_prob : leg.under_prob
    return product * (Math.max(legWinProb || 50, 1) / 100)
  }, 1)

  let correlationScore = 0
  for (let i = 0; i < legs.length; i += 1) {
    for (let j = i + 1; j < legs.length; j += 1) {
      correlationScore += correlationBetween(legs[i], legs[j])
    }
  }

  const expectedValue = impliedWinRate * (decimalOdds - 1) - (1 - impliedWinRate)

  return {
    id: legs.map((leg) => `${leg.player_id}-${leg.stat_type}`).join('-'),
    legs,
    legCount: legs.length,
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

export default function BetsPage() {
  const { data: edges = [], isLoading } = useEdgeFinder('', '', 4)
  const [trackedParlays, setTrackedParlays] = useState<TrackedParlay[]>(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  })

  const candidateEdges = useMemo(
    () => edges
      .filter((edge) => edge.recommendation !== 'PASS')
      .sort((a, b) => ((b.expected_value || b.edge_pct) - (a.expected_value || a.edge_pct)))
      .slice(0, 12),
    [edges]
  )

  const bestByLegCount = useMemo(() => {
    const sizes = [2, 4, 6]
    const output: Record<number, ParlayRecommendation[]> = {}

    sizes.forEach((size) => {
      if (candidateEdges.length < size) {
        output[size] = []
        return
      }

      const combos = makeParlayCombo(candidateEdges, size)
      output[size] = combos
        .map(toRecommendation)
        .sort((a, b) => (b.expectedValue + b.correlationScore * 0.04) - (a.expectedValue + a.correlationScore * 0.04))
        .slice(0, 3)
    })

    return output
  }, [candidateEdges])

  const strategy442 = useMemo(() => {
    const twoLegA = bestByLegCount[2]?.[0]
    const twoLegB = bestByLegCount[2]?.[1]

    if (!twoLegA || !twoLegB) return []

    const fourLegEdges = [...twoLegA.legs, ...twoLegB.legs].slice(0, 4)
    const fourLegger = toRecommendation(fourLegEdges)

    return [
      { label: '$4 - 2 Legger A', stake: 4, parlay: twoLegA },
      { label: '$4 - 2 Legger B', stake: 4, parlay: twoLegB },
      { label: '$2 - Combined 4 Legger', stake: 2, parlay: fourLegger },
    ]
  }, [bestByLegCount])

  const persistTracked = (next: TrackedParlay[]) => {
    setTrackedParlays(next)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  }

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
    return {
      totalStaked,
      pnl,
      roi: totalStaked ? (pnl / totalStaked) * 100 : 0,
    }
  }, [trackedParlays])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Parlay Builder</h1>
        <p className="text-muted-foreground">Recommended 2-leg, 4-leg, and 6-leg parlays with lightweight correlation scoring + bankroll tracking.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
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
              <h2 className="text-xl font-semibold">Best {size}-Leggers</h2>
              <div className="grid lg:grid-cols-3 gap-3">
                {(bestByLegCount[size] || []).map((parlay, idx) => (
                  <div key={parlay.id} className="rounded-lg border border-border p-4 bg-card space-y-3">
                    <div className="flex justify-between items-center">
                      <div className="font-semibold">#{idx + 1} ({parlay.legCount} legs)</div>
                      <div className="text-sm text-primary">{parlay.combinedOdds > 0 ? `+${parlay.combinedOdds}` : parlay.combinedOdds}</div>
                    </div>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {parlay.legs.map((leg) => (
                        <li key={`${leg.player_id}-${leg.stat_type}`}>{leg.player_name} {leg.recommendation} {leg.stat_type} ({leg.line})</li>
                      ))}
                    </ul>
                    <div className="text-xs text-muted-foreground">Corr: {parlay.correlationScore.toFixed(2)} | Est Win: {(parlay.impliedWinRate * 100).toFixed(1)}% | EV: {(parlay.expectedValue * 100).toFixed(1)}%</div>
                    <button onClick={() => addTrackedParlay(`${size}-Legger #${idx + 1}`, 5, parlay)} className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium">
                      Track for $5
                    </button>
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
