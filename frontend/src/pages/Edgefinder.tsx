import { useState } from 'react'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import { EdgesTable } from '@/components/tables/EdgesTable'
import { STAT_TYPES, POSITIONS } from '@/lib/constants'
import { Filter } from 'lucide-react'


/**
 * Edge Finder - Filterable table of all edges
 */
export default function EdgeFinder() {
  // Filters
  const [statType, setStatType] = useState<string>('')
  const [minEdge, setMinEdge] = useState<number>(3.0)
  const [position, setPosition] = useState<string>('')
  

  const { data: edges, isLoading, error } = useEdgeFinder(
    statType || undefined,
    'fanduel',
    minEdge,
    position || undefined
  )

  const processedEdges = edges || []


  const clearFilters = () => {
    setStatType('')
    setMinEdge(3.0)
    setPosition('')
  }

  const hasFilters = statType || minEdge !== 3.0 || position

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Edge Finder</h1>
        <p className="text-muted-foreground mt-2">
          Find and filter the best prop betting edges across all players
        </p>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Filters</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Stat Type Filter */}
          <div>
            <label className="text-sm font-medium mb-2 block">Stat Type</label>
            <select
              value={statType}
              onChange={(e) => setStatType(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Stats</option>
              {Object.entries(STAT_TYPES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Position Filter */}
          <div>
            <label className="text-sm font-medium mb-2 block">Position</label>
            <select
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Positions</option>
              {POSITIONS.map((pos) => (
                <option key={pos.value} value={pos.value}>
                  {pos.label}
                </option>
              ))}
            </select>
          </div>

          {/* Min Edge Filter */}
          <div>
            <label className="text-sm font-medium mb-2 block">
              Min Edge: {minEdge}%
            </label>
            <input
              type="range"
              min="0"
              max="20"
              step="1"
              value={minEdge}
              onChange={(e) => setMinEdge(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>0%</span>
              <span>20%</span>
            </div>
          </div>
        </div>

        {/* Clear Filters Button */}
        {hasFilters && (
          <div className="mt-4 pt-4 border-t border-border">
            <button
              onClick={clearFilters}
              className="text-sm text-muted-foreground hover:text-primary transition-colors"
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>

      {/* Results Count */}
      {!isLoading && processedEdges && (
        <div className="text-sm text-muted-foreground">
          Showing {processedEdges.length} edge{processedEdges.length !== 1 ? 's' : ''}
          {hasFilters && ' with current filters'}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4">
          <div className="text-red-400 font-medium">Error loading edges</div>
          <div className="text-red-400/80 text-sm mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        </div>
      )}

      {/* Edges Table */}
      <EdgesTable
        edges={processedEdges}
        isLoading={isLoading}
        emptyTitle={'No edges found'}
        emptyDescription={'Try adjusting your filters or check back later'}
      />
    </div>
  )
}
