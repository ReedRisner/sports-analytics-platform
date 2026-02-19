import { useEdgeFinder } from '@/hooks/useEdgeFinder'
import { BetCard } from '@/components/projections/BetCard'
import { TrendingUp } from 'lucide-react'
import type { Edge } from '@/api/types'

/**
 * Dashboard - Best Bets of the Day
 */
export default function Dashboard() {
  // Fetch FanDuel lines only with minimum 3% edge
  // Force FanDuel to keep it simple and fast
  const { data: edgesResponse, isLoading, error } = useEdgeFinder(
    undefined,        // stat_type: all
    'fanduel',        // sportsbook: FanDuel only
    3.0,              // min_edge: 3%
    undefined         // position: all
  )

  // Extract edges array from response (backend returns { edges: [...] })
  const edges: Edge[] = Array.isArray(edgesResponse) 
    ? edgesResponse 
    : (edgesResponse as any)?.edges || []

  // Filter out steals and blocks
  const filteredEdges = edges.filter((edge: Edge) => 
    edge.stat_type !== 'steals' && edge.stat_type !== 'blocks'
  )

  // Get top 10 bets sorted by absolute edge percentage (across ALL stats)
  const topBets = filteredEdges
    .sort((a: Edge, b: Edge) => Math.abs(b.edge_pct) - Math.abs(a.edge_pct))
    .slice(0, 10)

  const totalBetsFound = filteredEdges.length

  return (
    <div className="space-y-10 pb-12">
      {/* Sleek Header */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-transparent to-primary/20 blur-2xl" />
        
        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-5xl font-black tracking-tight bg-gradient-to-r from-black via-black to-black/60 bg-clip-text text-transparent">
              Today's Best Bets
            </h1>
            <div className="text-right">
              <div className="text-sm text-muted-foreground font-medium">
                {new Date().toLocaleDateString('en-US', { 
                  weekday: 'long'
                })}
              </div>
              <div className="text-2xl font-bold">
                {new Date().toLocaleDateString('en-US', { 
                  month: 'short', 
                  day: 'numeric',
                  year: 'numeric' 
                })}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-6 mt-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm text-muted-foreground">
                <span className="font-bold text-foreground">{totalBetsFound}</span> edges found
              </span>
            </div>
            {topBets.length > 0 && (
              <>
                <div className="h-4 w-px bg-border" />
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    Top edge: <span className="font-bold text-green-400">
                      +{Math.abs(topBets[0].edge_pct).toFixed(1)}%
                    </span>
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-muted-foreground">Finding the best bets...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-red-500/50 bg-red-500/10 p-8 text-center">
          <div className="text-red-400 font-semibold text-lg mb-2">Unable to load bets</div>
          <div className="text-red-400/80 text-sm">
            {error instanceof Error ? error.message : 'Unknown error occurred'}
          </div>
          <div className="text-red-400/60 text-sm mt-2">
            Make sure your backend is running at http://localhost:8000
          </div>
        </div>
      )}

      {/* Top 10 Bets Grid */}
      {!isLoading && !error && topBets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          {topBets.map((edge: Edge, index: number) => (
            <BetCard key={`${edge.player_id}-${edge.stat_type}-${index}`} edge={edge} rank={index + 1} />
          ))}
        </div>
      )}

      {/* No Bets Found */}
      {!isLoading && !error && topBets.length === 0 && (
        <div className="rounded-xl border border-border bg-card/50 p-12 text-center">
          <div className="text-muted-foreground text-lg mb-2">No bets found today</div>
          <p className="text-sm text-muted-foreground">
            Check back later or adjust your filters
          </p>
        </div>
      )}
    </div>
  )
}