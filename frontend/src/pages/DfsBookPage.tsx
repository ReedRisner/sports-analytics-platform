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

function getRecommendedProbability(edge: Edge): number {
  return edge.recommendation === 'OVER' ? edge.over_prob : edge.under_prob
}

function getStreakLength(edge: Edge): number {
  return edge.streak?.current_streak ?? 0
}

function sortByBestLine(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => {
    const aProb = getRecommendedProbability(a)
    const bProb = getRecommendedProbability(b)
    const aDisplayProb = aProb > 1 ? aProb : aProb * 100
    const bDisplayProb = bProb > 1 ? bProb : bProb * 100

    const probDiff = bDisplayProb - aDisplayProb
    if (Math.abs(probDiff) > 0.01) return probDiff

    return Math.abs(b.edge_pct) - Math.abs(a.edge_pct)
  })
}

function sortByLongestStreak(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => {
    const streakDiff = getStreakLength(b) - getStreakLength(a)
    if (streakDiff !== 0) return streakDiff

    return Math.abs(b.edge_pct) - Math.abs(a.edge_pct)
  })
}

function sortByEdge(edges: Edge[]): Edge[] {
  return [...edges].sort((a, b) => Math.abs(b.edge_pct) - Math.abs(a.edge_pct))
}

export default function DfsBookPage({ title, sportsbook, description, notes = [] }: DfsBookPageProps) {
  const [statType, setStatType] = useState<string>('')
  const [position, setPosition] = useState<string>('')
  const [minEdge, setMinEdge] = useState<number>(2)

  const { data: edges, isLoading, error } = useEdgeFinder(
    statType || undefined,
    sportsbook,
    minEdge,
    position || undefined
  )

  const filteredEdges = edges || []

  const bestLines = useMemo(() => sortByBestLine(filteredEdges).slice(0, 8), [filteredEdges])
  const longestStreaks = useMemo(() => sortByLongestStreak(filteredEdges).slice(0, 8), [filteredEdges])
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

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Best lines to take</div>
          <div className="mt-1 text-2xl font-semibold">{bestLines.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Top recommended lines by win probability + edge</div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Longest streak lines</div>
          <div className="mt-1 text-2xl font-semibold">{longestStreaks.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Hot hit/miss streak props (including alternate lines)</div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-sm text-muted-foreground">Total qualified lines</div>
          <div className="mt-1 text-2xl font-semibold">{filteredEdges.length}</div>
          <div className="text-xs text-muted-foreground mt-1">Filtered by stat, position, and minimum edge</div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Filters</h2>
        <div className="grid gap-4 md:grid-cols-3">
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
          <h3 className="text-lg font-semibold mb-3">Best lines to take</h3>
          <EdgesTable
            edges={bestLines}
            isLoading={isLoading}
            emptyTitle="No high-quality lines found"
            emptyDescription="Try lowering minimum edge or widening filters"
          />
        </div>
        <div>
          <h3 className="text-lg font-semibold mb-3">Longest over/under streaks</h3>
          <EdgesTable
            edges={longestStreaks}
            isLoading={isLoading}
            emptyTitle="No streak-based lines found"
            emptyDescription="Alternate/goblin lines will appear here when available"
          />
        </div>
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
