/**
 * Matchup Rankings - Softest/hardest defenses
 */
export default function MatchupRankings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Matchup Rankings</h1>
        <p className="text-muted-foreground mt-2">
          Find the easiest matchups by position and stat
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-4 flex-wrap">
        <div className="rounded-md border border-border bg-card p-3 text-sm text-muted-foreground">
          Stat type filter coming soon...
        </div>
      </div>

      {/* Rankings table */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Defense Rankings</h2>
        <p className="text-muted-foreground text-sm">
          Rankings table coming soon...
        </p>
      </div>
    </div>
  )
}