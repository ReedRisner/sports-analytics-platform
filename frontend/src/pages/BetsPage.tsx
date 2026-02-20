import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import type { Edge } from '@/api/types'

type BetResult = 'pending' | 'won' | 'lost' | 'push'
type ParlayStrategy = 'edge' | 'streak' | 'vegas' | 'custom'

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

function probabilityToAmerican(probabilityPct?: number) {
  if (!probabilityPct || probabilityPct <= 0 || probabilityPct >= 100) return -110
  const probability = probabilityPct / 100
  const decimal = 1 / probability
  return decimalToAmerican(decimal)
}

function getLegOdds(leg: Edge) {
  const rawOdds = leg.recommendation === 'OVER' ? leg.over_odds : leg.under_odds
  return rawOdds || -110
}

function getNoVigOdds(leg: Edge) {
  const fairProb = leg.recommendation === 'OVER' ? leg.no_vig_fair_over : leg.no_vig_fair_under
  return probabilityToAmerican(fairProb)
}

function correlationBetween(a: Edge, b: Edge) {
  let score = 0

  if (a.team_abbr === b.team_abbr) score += 0.4
  if (a.opp_abbr === b.opp_abbr && a.team_abbr === b.team_abbr) score += 0.2
  if ((a.stat_type === 'assists' && b.stat_type === 'points') || (a.stat_type === 'points' && b.stat_type === 'assists')) score += 0.3
  if ((a.stat_type === 'rebounds' && b.stat_type === 'points') || (a.stat_type === 'points' && b.stat_type === 'rebounds')) score -= 0.1

  return score
}

function buildRecommendation(legs: Edge[], strategy: ParlayStrategy, useNoVigOdds = false): ParlayRecommendation {
  const decimalOdds = legs.reduce((total, leg) => {
    const sourceOdds = useNoVigOdds ? getNoVigOdds(leg) : getLegOdds(leg)
    return total * americanToDecimal(sourceOdds)
  }, 1)

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

function takeTopUniquePlayers(
  edges: Edge[],
  size: number,
  scorer: (edge: Edge) => number,
  canAddLeg?: (selected: Edge[], candidate: Edge) => boolean
) {
  const used = new Set<number>()
  const selected: Edge[] = []

  const sorted = [...edges].sort((a, b) => scorer(b) - scorer(a))
  for (const edge of sorted) {
    if (used.has(edge.player_id)) continue
    if (canAddLeg && !canAddLeg(selected, edge)) continue
    selected.push(edge)
    used.add(edge.player_id)
    if (selected.length === size) break
  }

  return selected
}

function payout(stake: number, toWin: number, result: BetResult) {
  if (result === 'won') return toWin
  if (result === 'lost') return -stake
  return 0
}

function strategyLabel(strategy: ParlayStrategy) {
  if (strategy === 'edge') return 'Best Edge%'
  if (strategy === 'streak') return 'Best Streak'
  if (strategy === 'vegas') return 'Highest No-Vig Odds'
  return 'Custom Parlay'
}

export default function BetsPage() {
  const { data: edges = [], isLoading } = useEdgeFinder('', 'fanduel', 4)

  const [bankroll, setBankroll] = useState<number>(() => {
    const raw = localStorage.getItem(BANKROLL_STORAGE_KEY)
    const value = raw ? Number(raw) : 100
    return Number.isFinite(value) && value >= 0 ? value : 100
  })

  const [trackedParlays, setTrackedParlays] = useState<TrackedParlay[]>(() => {
    const raw = localStorage.getItem(TRACKER_STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  })

  const [stakeInputs, setStakeInputs] = useState<Record<string, number>>({})
  const [customLegCount, setCustomLegCount] = useState<number>(2)
  const [customStake, setCustomStake] = useState<number>(5)
  const [customLegKeys, setCustomLegKeys] = useState<string[]>([])

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
    () => {
      const fanduelEdges = edges.filter((edge) => edge.sportsbook?.toLowerCase() === 'fanduel')
      const source = fanduelEdges.length > 0 ? fanduelEdges : edges

      return source
        .filter((edge) => edge.recommendation !== 'PASS')
        .sort((a, b) => ((b.expected_value || b.edge_pct) - (a.expected_value || a.edge_pct)))
        .slice(0, 50)
    },
    [edges]
  )

  const parlaysByLegCount = useMemo(() => {
    const sizes = [2, 4, 6]
    const output: Record<number, ParlayRecommendation[]> = { 2: [], 4: [], 6: [] }

    sizes.forEach((size) => {
      const preventSameTeamInTwoLeg = (selected: Edge[], candidate: Edge) => (size !== 2 || selected.length === 0 || selected[0].team_abbr !== candidate.team_abbr)

      const edgeLegs = takeTopUniquePlayers(candidateEdges, size, (edge) => edge.edge_pct || 0, preventSameTeamInTwoLeg)
      const streakLegs = takeTopUniquePlayers(
        candidateEdges,
        size,
        (edge) => ((edge.streak?.current_streak || 0) * 100) + (edge.streak?.hit_rate || 0),
        preventSameTeamInTwoLeg
      )
      const vegasLegs = takeTopUniquePlayers(candidateEdges, size, (edge) => americanToDecimal(getNoVigOdds(edge)), preventSameTeamInTwoLeg)

      if (edgeLegs.length === size) {
        output[size].push(buildRecommendation(edgeLegs, 'edge'))
      }
      if (streakLegs.length === size) {
        output[size].push(buildRecommendation(streakLegs, 'streak'))
      }
      if (vegasLegs.length === size) {
        output[size].push(buildRecommendation(vegasLegs, 'vegas', true))
      }
    })

    return output
  }, [candidateEdges])

  const strategy442 = useMemo(() => {
    const twoLeg = parlaysByLegCount[2]
    if (twoLeg.length < 2) return []

    const first = twoLeg[0]
    const second = twoLeg[1]
    const merged = [...first.legs, ...second.legs]
    const uniqueMerged = takeTopUniquePlayers(merged, 4, (edge) => edge.edge_pct || 0)
    if (uniqueMerged.length < 4) return []

    const fourLegger = buildRecommendation(uniqueMerged, 'edge')

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

  const removeTrackedParlay = (id: string) => {
    persistTracked(trackedParlays.filter((bet) => bet.id !== id))
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

  const customParlayCandidate = useMemo(() => {
    const chosen = customLegKeys
      .map((key) => candidateEdges.find((edge) => `${edge.player_id}-${edge.stat_type}-${edge.recommendation}` === key))
      .filter((edge): edge is Edge => Boolean(edge))

    const uniqueChosen = takeTopUniquePlayers(chosen, chosen.length, (edge) => edge.edge_pct || 0)
    if (uniqueChosen.length !== chosen.length || chosen.length !== customLegCount) return null
    if (customLegCount === 2 && uniqueChosen[0]?.team_abbr === uniqueChosen[1]?.team_abbr) return null

    return buildRecommendation(uniqueChosen, 'custom')
  }, [customLegKeys, candidateEdges, customLegCount])

  const toggleCustomLeg = (edge: Edge) => {
    const key = `${edge.player_id}-${edge.stat_type}-${edge.recommendation}`

    setCustomLegKeys((current) => {
      if (current.includes(key)) return current.filter((existing) => existing !== key)

      const selectedPlayerIds = new Set(
        current
          .map((existing) => candidateEdges.find((item) => `${item.player_id}-${item.stat_type}-${item.recommendation}` === existing)?.player_id)
          .filter((id): id is number => typeof id === 'number')
      )

      if (selectedPlayerIds.has(edge.player_id)) return current

      if (customLegCount === 2 && current.length === 1) {
        const existing = candidateEdges.find((item) => `${item.player_id}-${item.stat_type}-${item.recommendation}` === current[0])
        if (existing && existing.team_abbr === edge.team_abbr) return current
      }

      if (current.length >= customLegCount) return current

      return [...current, key]
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Parlay Builder</h1>
        <p className="text-muted-foreground">Top parlays by Edge%, Streak, and No-Vig odds using FanDuel lines. Every parlay requires unique players.</p>
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
        <div className="rounded-lg border border-border p-4 bg-card"><div className="text-xs text-muted-foreground">Current Bankroll</div><div className="text-2xl font-bold">${bankrollSummary.currentBankroll.toFixed(2)}</div></div>
        <div className="rounded-lg border border-border p-4 bg-card"><div className="text-xs text-muted-foreground">Total Staked</div><div className="text-2xl font-bold">${bankrollSummary.totalStaked.toFixed(2)}</div></div>
        <div className="rounded-lg border border-border p-4 bg-card"><div className="text-xs text-muted-foreground">Net P/L</div><div className={`text-2xl font-bold ${bankrollSummary.pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>{bankrollSummary.pnl >= 0 ? '+' : ''}${bankrollSummary.pnl.toFixed(2)}</div></div>
        <div className="rounded-lg border border-border p-4 bg-card"><div className="text-xs text-muted-foreground">ROI</div><div className={`text-2xl font-bold ${bankrollSummary.roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>{bankrollSummary.roi >= 0 ? '+' : ''}{bankrollSummary.roi.toFixed(1)}%</div></div>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-border p-6 text-muted-foreground">Building recommended parlays...</div>
      ) : (
        <div className="space-y-6">
          {[2, 4, 6].map((size) => (
            <section key={size} className="space-y-3">
              <h2 className="text-xl font-semibold">{size}-Leggers (3 Strategies)</h2>
              <div className="grid lg:grid-cols-3 gap-3">
                {(parlaysByLegCount[size] || []).map((parlay) => {
                  const stakeValue = stakeInputs[parlay.id] ?? suggestedUnitStake
                  return (
                    <div key={parlay.id} className="rounded-lg border border-border p-4 bg-card space-y-3">
                      <div className="flex justify-between items-center">
                        <div className="font-semibold">{strategyLabel(parlay.strategy)}</div>
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
                      <div className="text-xs text-muted-foreground">Corr: {parlay.correlationScore.toFixed(2)} | Est Win: {(parlay.impliedWinRate * 100).toFixed(1)}% | EV: {(parlay.expectedValue * 100).toFixed(1)}%</div>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={stakeValue}
                          onChange={(event) => setStakeInputs((curr) => ({ ...curr, [parlay.id]: Number(event.target.value) || 1 }))}
                          className="w-24 px-2 py-1 rounded border border-border bg-background text-sm"
                        />
                        <button onClick={() => addTrackedParlay(`${size}-Legger ${strategyLabel(parlay.strategy)}`, stakeValue, parlay)} className="flex-1 rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium">
                          Place Parlay
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          ))}

          <section className="space-y-3">
            <h2 className="text-xl font-semibold">Build Custom Parlay</h2>
            <div className="rounded-lg border border-border p-4 bg-card space-y-3">
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Leg Count</label>
                  <select
                    value={customLegCount}
                    onChange={(event) => {
                      const count = Number(event.target.value)
                      setCustomLegCount(count)
                      setCustomLegKeys([])
                    }}
                    className="px-3 py-2 rounded border border-border bg-background text-sm"
                  >
                    <option value={2}>2</option>
                    <option value={4}>4</option>
                    <option value={6}>6</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Stake ($)</label>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={customStake}
                    onChange={(event) => setCustomStake(Number(event.target.value) || 1)}
                    className="w-24 px-3 py-2 rounded border border-border bg-background text-sm"
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-80 overflow-y-auto">
                {candidateEdges.map((edge) => {
                  const key = `${edge.player_id}-${edge.stat_type}-${edge.recommendation}`
                  const selected = customLegKeys.includes(key)
                  const selectedPlayers = new Set(customLegKeys.map((existing) => candidateEdges.find((item) => `${item.player_id}-${item.stat_type}-${item.recommendation}` === existing)?.player_id).filter((id): id is number => typeof id === 'number'))
                  const disabled = !selected && (customLegKeys.length >= customLegCount || selectedPlayers.has(edge.player_id))

                  return (
                    <button
                      key={key}
                      disabled={disabled}
                      onClick={() => toggleCustomLeg(edge)}
                      className={`text-left rounded border p-2 text-sm ${selected ? 'border-primary bg-primary/10' : 'border-border'} ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
                    >
                      <div className="font-medium">{edge.player_name}</div>
                      <div className="text-xs text-muted-foreground">{edge.recommendation} {edge.stat_type} ({edge.line}) • Edge {edge.edge_pct?.toFixed(1)}%</div>
                    </button>
                  )
                })}
              </div>

              {customParlayCandidate && (
                <div className="rounded border border-border p-3">
                  <div className="font-medium mb-1">Custom parlay ready ({customParlayCandidate.legCount} legs)</div>
                  <div className="text-sm text-muted-foreground mb-2">Odds: {customParlayCandidate.combinedOdds > 0 ? `+${customParlayCandidate.combinedOdds}` : customParlayCandidate.combinedOdds}</div>
                  <button onClick={() => addTrackedParlay('Custom Parlay', customStake, customParlayCandidate)} className="rounded-md bg-primary text-primary-foreground px-3 py-2 text-sm font-medium">
                    Place Custom Parlay
                  </button>
                </div>
              )}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-xl font-semibold">Recommended 4/4/2 Strategy ($10)</h2>
            <div className="grid lg:grid-cols-3 gap-3">
              {strategy442.map((entry) => (
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
        <h2 className="text-xl font-semibold">Placed Parlays</h2>
        <div className="space-y-2">
          {trackedParlays.length === 0 && <div className="rounded-lg border border-border p-4 text-muted-foreground">No placed parlays yet.</div>}
          {trackedParlays.map((bet) => (
            <div key={bet.id} className="rounded-lg border border-border p-3 bg-card flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-medium">{bet.label}</div>
                <div className="text-sm text-muted-foreground">Stake ${bet.stake.toFixed(2)} | To Win ${bet.toWin.toFixed(2)}</div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {(['pending', 'won', 'lost', 'push'] as BetResult[]).map((result) => (
                  <button key={result} onClick={() => updateResult(bet.id, result)} className={`px-3 py-1 rounded-md text-sm border ${bet.result === result ? 'border-primary text-primary' : 'border-border text-muted-foreground'}`}>
                    {result}
                  </button>
                ))}
                <button onClick={() => removeTrackedParlay(bet.id)} className="px-3 py-1 rounded-md text-sm border border-red-500/50 text-red-400 hover:bg-red-500/10">
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
