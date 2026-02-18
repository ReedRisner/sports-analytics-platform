import { useState } from 'react'
import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import { EdgesTable } from '@/components/tables/EdgesTable'
import { STAT_TYPES, SPORTSBOOKS, POSITIONS } from '@/lib/constants'
import { Filter, SortAsc, SortDesc } from 'lucide-react'

type SortField = 'edge_pct' | 'projected' | 'line' | 'over_prob'
type SortDirection = 'asc' | 'desc'

/**
 * Edge Finder - Filterable table of all edges
 */
export default function EdgeFinder() {
  // Filters
  const [statType, setStatType] = useState<string>('')
  const [sportsbook, setSportsbook] = useState<string>('')
  const [minEdge, setMinEdge] = useState<number>(3.0)
  const [position, setPosition] = useState<string>('')
  
  // Sorting
  const [sortField, setSortField] = useState<SortField>('edge_pct')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  // Fetch edges with filters
  const { data: edges, isLoading, error } = useEdgeFinder(
    statType || undefined,
    sportsbook || undefined,
    minEdge,
    position || undefined
  )

  // Sort edges
  const sortedEdges = edges ? [...edges].sort((a, b) => {
    let aVal: number, bVal: number

    switch (sortField) {
      case 'edge_pct':
        aVal = Math.abs(a.edge_pct)
        bVal = Math.abs(b.edge_pct)
        break
      case 'projected':
        aVal = a.projected
        bVal = b.projected
        break
      case 'line':
        aVal = a.line
        bVal = b.line
        break
      case 'over_prob':
        aVal = a.recommendation === 'OVER' ? a.over_prob : a.under_prob
        bVal = b.recommendation === 'OVER' ? b.over_prob : b.under_prob
        break
      default:
        return 0
    }

    return sortDirection === 'desc' ? bVal - aVal : aVal - bVal
  }) : []

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // Toggle direction
      setSortDirection(sortDirection === 'desc' ? 'asc' : 'desc')
    } else {
      // New field, default to descending
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const clearFilters = () => {
    setStatType('')
    setSportsbook('')
    setMinEdge(3.0)
    setPosition('')
  }

  const hasFilters = statType || sportsbook || minEdge !== 3.0 || position

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

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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

          {/* Sportsbook Filter */}
          <div>
            <label className="text-sm font-medium mb-2 block">Sportsbook</label>
            <select
              value={sportsbook}
              onChange={(e) => setSportsbook(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Sportsbooks</option>
              {SPORTSBOOKS.map((book) => (
                <option key={book.value} value={book.value}>
                  {book.label}
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

      {/* Sorting Controls */}
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-sm font-medium">Sort by:</span>
        
        <button
          onClick={() => handleSort('edge_pct')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md border transition-colors ${
            sortField === 'edge_pct'
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border hover:border-primary/50'
          }`}
        >
          <span className="text-sm">Edge %</span>
          {sortField === 'edge_pct' && (
            sortDirection === 'desc' ? <SortDesc className="w-4 h-4" /> : <SortAsc className="w-4 h-4" />
          )}
        </button>

        <button
          onClick={() => handleSort('projected')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md border transition-colors ${
            sortField === 'projected'
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border hover:border-primary/50'
          }`}
        >
          <span className="text-sm">Projection</span>
          {sortField === 'projected' && (
            sortDirection === 'desc' ? <SortDesc className="w-4 h-4" /> : <SortAsc className="w-4 h-4" />
          )}
        </button>

        <button
          onClick={() => handleSort('over_prob')}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-md border transition-colors ${
            sortField === 'over_prob'
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border hover:border-primary/50'
          }`}
        >
          <span className="text-sm">Win Probability</span>
          {sortField === 'over_prob' && (
            sortDirection === 'desc' ? <SortDesc className="w-4 h-4" /> : <SortAsc className="w-4 h-4" />
          )}
        </button>

        {isLoading && (
          <div className="flex items-center gap-2 ml-auto">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-muted-foreground">Updating...</span>
          </div>
        )}
      </div>

      {/* Results Count */}
      {!isLoading && sortedEdges && (
        <div className="text-sm text-muted-foreground">
          Showing {sortedEdges.length} edge{sortedEdges.length !== 1 ? 's' : ''}
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
      <EdgesTable edges={sortedEdges} isLoading={isLoading} />
    </div>
  )
}