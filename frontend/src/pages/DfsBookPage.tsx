import { useMemo, useState } from 'react'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import { EdgesTable } from '@/components/tables/EdgesTable'
import { STAT_TYPES, POSITIONS } from '@/lib/constants'
import type { Edge } from '@/api/types'

interface DfsBookPageProps {
  title: string
  sportsbook: 'prizepicks' | 'underdog'
  description: string
  notes?: string[]
}

type LineTypeFilter = 'all' | 'goblin' | 'demon' | 'normal'

function getRecommendedProbability(edge: Edge): number {
  return edge.recommendation === 'OVER' ? edge.over_prob : edge.under_prob
}

function getDisplayProbability(edge: Edge): number {
  const prob = getRecommendedProbability(edge)
  return prob > 1 ? prob : prob * 100
}

function getRecommendedOdds(edge: Edge): number {
  return edge.recommendation === 'OVER' ? (edge.over_odds ?? -119) : (edge.under_odds ?? -119)
}

function getStreakLength(edge: Edge): number {
  return edge.streak?.current_streak ?? 0
}

function classifyLineType(edge: Edge): Exclude<LineTypeFilter, 'all'> {
  const recOdds = getRecommendedOdds(edge)

  // DFS books: plus-money adjusted lines are higher-risk demon style.
  if (recOdds >= 100) {
    return 'demon'
  }

  // Favor "safe" lower adjusted lines as goblins.
  if (recOdds <= -130) {
    return 'goblin'
  }

  return 'normal'
}

function sortBySafestGoblin(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => {
    const streakDiff = getStreakLength(b) - getStreakLength(a)
    if (streakDiff !== 0) return streakDiff

    const probDiff = getDisplayProbability(b) - getDisplayProbability(a)
    if (Math.abs(probDiff) > 0.01) return probDiff

    return Math.abs(b.edge_pct) - Math.abs(a.edge_pct)
  })
}

function sortByRiskyDemonOver(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => {
    const aScore = getDisplayProbability(a) * 0.6 + Math.abs(a.edge_pct) * 0.4
    const bScore = getDisplayProbability(b) * 0.6 + Math.abs(b.edge_pct) * 0.4
    return bScore - aScore
  })
}

function sortByBestFive(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => {
    const aStreakBonus = Math.min(getStreakLength(a), 8) * 2
    const bStreakBonus = Math.min(getStreakLength(b), 8) * 2

    const aScore = getDisplayProbability(a) + Math.abs(a.edge_pct) + aStreakBonus
    const bScore = getDisplayProbability(b) + Math.abs(b.edge_pct) + bStreakBonus

    return bScore - aScore
  })
}

function sortByEdge(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => Math.abs(b.edge_pct) - Math.abs(a.edge_pct))
}

export default function DfsBookPage({ title, sportsbook, description, notes = [] }: DfsBookPageProps) {
  const [statType, setStatType] = useState<string>('')
  const [position, setPosition] = useState<string>('')
  const [lineType, setLineType] = useState<LineTypeFilter>('all')
  const [minEdge, setMinEdge] = useState<number>(2)

  const { data: edges, isLoading, error } = useEdgeFinder(
    statType || undefined,
    sportsbook,
    minEdge,
    position || undefined
  )

  const allEdges = edges || []

  const filteredEdges = useMemo(() => {
    if (lineType === 'all') return allEdges
    return allEdges.filter((edge) => classifyLineType(edge) === lineType)
  }, [allEdges, lineType])

  const safeGoblinStreaks = useMemo(
    () => sortBySafestGoblin(allEdges.filter((edge) => classifyLineType(edge) === 'goblin')).slice(0, 8),
    [allEdges]
  )

  const riskyDemonOvers = useMemo(
    () => sortByRiskyDemonOver(allEdges.filter((edge) => classifyLineType(edge) === 'demon' && edge.recommendation === 'OVER')).slice(0, 8),
    [allEdges]
  )

  const bestFivePicks = useMemo(() => sortByBestFive(filteredEdges).slice(0, 5), [filteredEdges])
  const strongestEdges = useMemo(() => sortByEdge(filteredEdges), [filteredEdges])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        <p className="text-muted-foreground mt-2">{description}</p>
      </div>

      {notes.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-2">
          <h2 className="text-lg font-semibold">Book-specific notes</h2>
          <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Safest goblin streaks</div>
          <div className="mt-1 text-2xl font-semibold">{safeGoblinStreaks.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Longest streaks on lower adjusted lines</div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Best demon risks</div>
          <div className="mt-1 text-2xl font-semibold">{riskyDemonOvers.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Top OVER demon/adjusted risk lines</div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Best 5 picks</div>
          <div className="mt-1 text-2xl font-semibold">{bestFivePicks.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Highest blended confidence for this DFS board</div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Total qualified lines</div>
          <div className="mt-1 text-2xl font-semibold">{filteredEdges.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Filtered by stat, position, edge, and line type</div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Filters</h2>
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Stat Type</label>
            <select
              value={statType}
              onChange={(e) => setStatType(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-sm"
            >
              <option value="">All Stats</option>
              {Object.entries(STAT_TYPES).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Position</label>
            <select
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-sm"
            >
              <option value="">All Positions</option>
              {POSITIONS.map((pos) => (
                <option key={pos.value} value={pos.value}>{pos.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Line Type</label>
            <select
              value={lineType}
              onChange={(e) => setLineType(e.target.value as LineTypeFilter)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-sm"
            >
              <option value="all">All Lines</option>
              <option value="goblin">Goblin / Safe Adjusted</option>
              <option value="demon">Demon / Risk Adjusted</option>
              <option value="normal">Normal Lines</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">Min Edge: {minEdge}%</label>
            <input
              type="range"
              min="0"
              max="20"
              step="1"
              value={minEdge}
              onChange={(e) => setMinEdge(Number(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4">
          <div className="text-red-400 font-medium">Error loading {title} lines</div>
          <div className="text-red-400/80 text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <div>
          <h3 className="text-lg font-semibold mb-3">Safest bets (goblin streaks)</h3>
          <EdgesTable
            edges={safeGoblinStreaks}
            isLoading={isLoading}
            emptyTitle="No goblin-safe streaks found"
            emptyDescription="Try lowering minimum edge or check when more adjusted lines are posted"
          />
        </div>
        <div>
          <h3 className="text-lg font-semibold mb-3">Best demon risk lines (OVER)</h3>
          <EdgesTable
            edges={riskyDemonOvers}
            isLoading={isLoading}
            emptyTitle="No demon risk lines found"
            emptyDescription="Demon/plus-money adjusted overs will appear here"
          />
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-3">Best 5 {title} picks</h3>
        <EdgesTable
          edges={bestFivePicks}
          isLoading={isLoading}
          emptyTitle="No top picks found"
          emptyDescription="Try reducing your filters"
        />
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-3">All recommended {title} lines</h3>
        <EdgesTable
          edges={strongestEdges}
          isLoading={isLoading}
          emptyTitle="No lines found"
          emptyDescription="Try reducing your filters"
        />
      </div>
    </div>
  )
}
