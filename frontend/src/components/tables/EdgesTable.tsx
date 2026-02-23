import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowDownUp, ArrowUp, ArrowDown, TrendingUp, TrendingDown } from 'lucide-react'
import { Edge } from '@/api/types'
import { EdgeIndicator } from '@/components/projections/EdgeIndicator'
import { RecommendationBadge } from '@/components/projections/RecommendationBadge'
import { StatBadge } from '@/components/projections/StatBadge'

interface EdgesTableProps {
  edges: Edge[]
  isLoading?: boolean
  emptyTitle?: string
  emptyDescription?: string
}

type SortField = 'player' | 'matchup' | 'stat' | 'line' | 'projected' | 'edge' | 'no_vig' | 'streak' | 'prob' | 'recommendation'
type SortDirection = 'asc' | 'desc'

const getDisplayProbability = (edge: Edge) => {
  const prob = edge.recommendation === 'OVER' ? edge.over_prob : edge.under_prob
  return prob > 1 ? prob : prob * 100
}

const getNoVigProbability = (edge: Edge) => {
  if (edge.recommendation === 'OVER') return edge.no_vig_fair_over ?? 0
  return edge.no_vig_fair_under ?? 0
}

/**
 * Table displaying edges with sorting and click-to-view
 */
export function EdgesTable({ edges, isLoading, emptyTitle = 'No edges found', emptyDescription = 'Try adjusting your filters or check back later' }: EdgesTableProps) {
  const navigate = useNavigate()
  const [sortField, setSortField] = useState<SortField>('edge')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const sortedEdges = useMemo(() => {
    const rows = [...edges]
    rows.sort((a, b) => {
      let aVal: number | string = 0
      let bVal: number | string = 0

      switch (sortField) {
        case 'player':
          aVal = a.player_name
          bVal = b.player_name
          break
        case 'matchup':
          aVal = `${a.team_abbr}-${a.opp_abbr}`
          bVal = `${b.team_abbr}-${b.opp_abbr}`
          break
        case 'stat':
          aVal = a.stat_type
          bVal = b.stat_type
          break
        case 'line':
          aVal = a.line
          bVal = b.line
          break
        case 'projected':
          aVal = a.projected
          bVal = b.projected
          break
        case 'edge':
          aVal = Math.abs(a.edge_pct)
          bVal = Math.abs(b.edge_pct)
          break
        case 'no_vig':
          aVal = getNoVigProbability(a)
          bVal = getNoVigProbability(b)
          break
        case 'streak':
          aVal = a.streak?.current_streak ?? 0
          bVal = b.streak?.current_streak ?? 0
          break
        case 'prob':
          aVal = getDisplayProbability(a)
          bVal = getDisplayProbability(b)
          break
        case 'recommendation':
          aVal = a.recommendation
          bVal = b.recommendation
          break
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }

      const numA = Number(aVal)
      const numB = Number(bVal)
      return sortDirection === 'asc' ? numA - numB : numB - numA
    })

    return rows
  }, [edges, sortDirection, sortField])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }

    setSortField(field)
    setSortDirection(field === 'player' || field === 'matchup' || field === 'stat' || field === 'recommendation' ? 'asc' : 'desc')
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowDownUp className="w-3.5 h-3.5 opacity-50" />
    return sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />
  }

  const HeaderCell = ({ field, title, align = 'text-left' }: { field: SortField; title: string; align?: string }) => (
    <th className={`p-4 text-sm font-medium text-muted-foreground ${align}`}>
      <button
        type="button"
        className={`inline-flex items-center gap-1.5 hover:text-foreground transition-colors ${align === 'text-center' ? 'justify-center w-full' : ''}`}
        onClick={() => handleSort(field)}
      >
        <span>{title}</span>
        <SortIcon field={field} />
      </button>
    </th>
  )

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center">
        <div className="text-muted-foreground">Loading edges...</div>
      </div>
    )
  }

  if (edges.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-12 text-center">
        <div className="text-muted-foreground">{emptyTitle}</div>
        <p className="text-sm text-muted-foreground mt-2">
          {emptyDescription}
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <HeaderCell field="player" title="Player" />
              <HeaderCell field="matchup" title="Matchup" />
              <HeaderCell field="stat" title="Stat" />
              <HeaderCell field="line" title="Line" align="text-center" />
              <HeaderCell field="projected" title="Proj" align="text-center" />
              <HeaderCell field="edge" title="Edge" align="text-center" />
              <HeaderCell field="no_vig" title="No-Vig" align="text-center" />
              <HeaderCell field="streak" title="Streak" align="text-center" />
              <HeaderCell field="prob" title="Prob" align="text-center" />
              <HeaderCell field="recommendation" title="Rec" align="text-center" />
            </tr>
          </thead>
          <tbody>
            {sortedEdges.map((edge, index) => (
              <tr
                key={`${edge.player_id}-${edge.stat_type}-${edge.line}-${index}`}
                onClick={() => navigate(`/player/${edge.player_id}`)}
                className="border-b border-border hover:bg-accent/50 cursor-pointer transition-colors"
              >
                <td className="p-4">
                  <div className="font-medium">{edge.player_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {edge.team_abbr} • {edge.position}
                  </div>
                </td>
                <td className="p-4">
                  <div className="text-sm">vs {edge.opp_abbr}</div>
                  {edge.matchup_grade && (
                    <div className="text-xs text-muted-foreground">
                      {edge.matchup_grade}
                    </div>
                  )}
                </td>
                <td className="p-4">
                  <StatBadge statType={edge.stat_type} />
                </td>
                <td className="p-4 text-center font-mono">
                  {edge.line.toFixed(1)}
                </td>
                <td className="p-4 text-center font-mono font-medium">
                  {edge.projected.toFixed(1)}
                </td>
                <td className="p-4 text-center">
                  <EdgeIndicator edge={edge.edge_pct} recommendation={edge.recommendation} />
                </td>
                <td className="p-4 text-center">
                  {edge.recommendation === 'OVER' && edge.no_vig_fair_over !== undefined ? (
                    <div className="font-mono text-sm">{(edge.no_vig_fair_over * 100).toFixed(1)}%</div>
                  ) : edge.recommendation === 'UNDER' && edge.no_vig_fair_under !== undefined ? (
                    <div className="font-mono text-sm">{(edge.no_vig_fair_under * 100).toFixed(1)}%</div>
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </td>
                <td className="p-4 text-center">
                  {edge.streak && edge.streak.current_streak > 0 ? (
                    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold ${
                      edge.streak.streak_type === 'hit' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {edge.streak.streak_type === 'hit' ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {edge.streak.current_streak}x
                    </div>
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </td>
                <td className="p-4 text-center font-mono text-sm">
                  {`${getDisplayProbability(edge).toFixed(1)}%`}
                </td>
                <td className="p-4 text-center">
                  <RecommendationBadge recommendation={edge.recommendation} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
