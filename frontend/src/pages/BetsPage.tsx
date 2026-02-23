import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import type { Edge } from '@/api/types'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'

type ParlayStrategy = 'best'

interface ParlayRecommendation {
  id: string
  legs: Edge[]
  legCount: number
  strategy: ParlayStrategy
  combinedOdds: number
  noVigHitProbability: number
}

function probabilityToAmerican(probabilityPct?: number) {
  if (!probabilityPct || probabilityPct <= 0 || probabilityPct >= 100) return -110
  const probability = probabilityPct / 100
  const decimal = 1 / probability
  if (decimal <= 1) return -10000
  if (decimal >= 2) return Math.round((decimal - 1) * 100)
  return Math.round(-100 / (decimal - 1))
}

function americanToDecimal(odds: number) {
  if (!odds) return 1.91
  return odds > 0 ? 1 + odds / 100 : 1 + 100 / Math.abs(odds)
}

function decimalToAmerican(decimal: number) {
  if (decimal <= 1) return -10000
  if (decimal >= 2) return Math.round((decimal - 1) * 100)
  return Math.round(-100 / (decimal - 1))
}

function getNoVigOdds(leg: Edge) {
  const fairProb = leg.recommendation === 'OVER' ? leg.no_vig_fair_over : leg.no_vig_fair_under
  return probabilityToAmerican(fairProb)
}

function getNoVigProbability(leg: Edge) {
  const fairProb = leg.recommendation === 'OVER' ? leg.no_vig_fair_over : leg.no_vig_fair_under
  return Math.max(Math.min((fairProb || 50) / 100, 0.99), 0.01)
}

function takeTopUniquePlayers(edges: Edge[], size: number, scorer: (edge: Edge) => number) {
  const used = new Set<number>()
  const selected: Edge[] = []

  const sorted = [...edges].sort((a, b) => scorer(b) - scorer(a))
  for (const edge of sorted) {
    if (used.has(edge.player_id)) continue
    selected.push(edge)
    used.add(edge.player_id)
    if (selected.length === size) break
  }

  return selected
}

function getCombinationSets<T>(items: T[], size: number): T[][] {
  const output: T[][] = []

  function backtrack(start: number, path: T[]) {
    if (path.length === size) {
      output.push([...path])
      return
    }

    for (let i = start; i < items.length; i += 1) {
      path.push(items[i])
      backtrack(i + 1, path)
      path.pop()
    }
  }

  backtrack(0, [])
  return output
}

function buildRecommendation(legs: Edge[]): ParlayRecommendation {
  const decimalOdds = legs.reduce((total, leg) => total * americanToDecimal(getNoVigOdds(leg)), 1)
  const noVigHitProbability = legs.reduce((total, leg) => total * getNoVigProbability(leg), 1)

  return {
    id: `best-${legs.map((leg) => `${leg.player_id}-${leg.stat_type}`).join('-')}`,
    legs,
    legCount: legs.length,
    strategy: 'best',
    combinedOdds: decimalToAmerican(decimalOdds),
    noVigHitProbability,
  }
}

function getMultiplierLabel(legCount: number) {
  if (legCount === 2) return 'x3'
  if (legCount === 4) return 'x10'
  if (legCount === 6) return 'x25'
  return 'x?'
}

export default function BetsPage() {
  const { data: edges = [], isLoading } = useEdgeFinder('', '', 4)

  const candidateEdges = useMemo(
    () => edges
      .filter((edge) => edge.recommendation !== 'PASS')
      .sort((a, b) => ((b.expected_value || b.edge_pct) - (a.expected_value || a.edge_pct)))
      .slice(0, 18),
    [edges]
  )

  const parlaysByLegCount = useMemo(() => {
    const sizes = [2, 4, 6]
    const output: Record<number, ParlayRecommendation[]> = { 2: [], 4: [], 6: [] }

    sizes.forEach((size) => {
      const uniquePool = takeTopUniquePlayers(candidateEdges, Math.max(size + 4, 10), (edge) => getNoVigProbability(edge))
      const combos = getCombinationSets(uniquePool, size)
      const ranked = combos
        .map((legs) => buildRecommendation(legs))
        .sort((a, b) => b.noVigHitProbability - a.noVigHitProbability)

      output[size] = ranked.slice(0, 3)
    })

    return output
  }, [candidateEdges])

  const strategy442 = useMemo(() => {
    const twoLeg = parlaysByLegCount[2]
    if (twoLeg.length < 2) return null

    const first = twoLeg[0]
    const second = twoLeg[1]
    const merged = [...first.legs, ...second.legs]
    const uniqueMerged = takeTopUniquePlayers(merged, 4, (edge) => getNoVigProbability(edge))
    if (uniqueMerged.length < 4) return null

    const fourLegger = buildRecommendation(uniqueMerged)

    return {
      first,
      second,
      fourLegger,
      totalNoVigHitProbability: first.noVigHitProbability * second.noVigHitProbability * fourLegger.noVigHitProbability,
    }
  }, [parlaysByLegCount])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Best Bets</h1>
        <p className="text-muted-foreground">Showing only best recommended parlays (2-leg, 4-leg, 6-leg) plus the top 4/4/2 method.</p>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-border p-6 text-muted-foreground">Building best bets...</div>
      ) : (
        <div className="space-y-6">
          {[2, 4, 6].map((size) => (
            <section key={size} className="space-y-3">
              <h2 className="text-xl font-semibold">Top 3 Best {size}-Leg Parlays <span className="text-primary">({getMultiplierLabel(size)})</span></h2>
              <div className="grid lg:grid-cols-3 gap-3">
                {(parlaysByLegCount[size] || []).map((parlay, index) => (
                  <div key={parlay.id} className="rounded-lg border border-border p-4 bg-card space-y-3">
                    <div className="flex justify-between items-center">
                      <div className="font-semibold">#{index + 1} Best {size}-Leg</div>
                      <div className="text-sm text-primary">{parlay.combinedOdds > 0 ? `+${parlay.combinedOdds}` : parlay.combinedOdds}</div>
                    </div>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {parlay.legs.map((leg) => (
                        <li key={`${parlay.id}-${leg.player_id}-${leg.stat_type}`}>
                          <Link className="hover:text-primary underline underline-offset-4" to={`/player/${leg.player_id}`}>
                            {leg.player_name}
                          </Link>{' '}
                          {leg.recommendation} {leg.stat_type} ({leg.line})
                        </li>
                      ))}
                    </ul>
                    <div className="text-xs text-muted-foreground">
                      No-Vig Vegas Odds of Hitting: {(parlay.noVigHitProbability * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}

          <section className="space-y-3">
            <h2 className="text-xl font-semibold">Best 4/4/2 Method</h2>
            {!strategy442 ? (
              <div className="rounded-lg border border-border p-4 text-muted-foreground">Not enough data for a 4/4/2 method right now.</div>
            ) : (
              <div className="grid lg:grid-cols-3 gap-3">
                {[
                  { label: 'First 2-Leg (x3)', parlay: strategy442.first },
                  { label: 'Second 2-Leg (x3)', parlay: strategy442.second },
                  { label: 'Combined 4-Leg (x10)', parlay: strategy442.fourLegger },
                ].map((entry) => (
                  <div key={entry.label} className="rounded-lg border border-border p-4 bg-card space-y-2">
                    <div className="font-semibold">{entry.label}</div>
                    <div className="text-sm text-primary">Odds: {entry.parlay.combinedOdds > 0 ? `+${entry.parlay.combinedOdds}` : entry.parlay.combinedOdds}</div>
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      {entry.parlay.legs.map((leg) => (
                        <li key={`${entry.label}-${leg.player_id}-${leg.stat_type}`}>
                          <Link className="hover:text-primary underline underline-offset-4" to={`/player/${leg.player_id}`}>{leg.player_name}</Link> {leg.recommendation} {leg.stat_type}
                        </li>
                      ))}
                    </ul>
                    <div className="text-xs text-muted-foreground">No-Vig Vegas Odds of Hitting: {(entry.parlay.noVigHitProbability * 100).toFixed(1)}%</div>
                  </div>
                ))}
              </div>
            )}
            {strategy442 && (
              <div className="text-sm text-muted-foreground">
                Full 4/4/2 Sequence No-Vig Hit Rate: {(strategy442.totalNoVigHitProbability * 100).toFixed(2)}%
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
