/**
 * Edge Finder - Filterable table of all edges
 */
export default function EdgeFinder() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Edge Finder</h1>
        <p className="text-muted-foreground mt-2">
          Find the best prop betting edges across all players
        </p>
      </div>

      {/* Filters (placeholder) */}
      <div className="flex gap-4 flex-wrap">
        <div className="rounded-md border border-border bg-card p-3 text-sm text-muted-foreground">
          Filters coming soon...
        </div>
      </div>

      {/* Table (placeholder) */}
      <div className="rounded-lg border border-border bg-card p-6">
        <p className="text-muted-foreground text-sm">
          Edge finder table coming soon...
        </p>
      </div>
    </div>
  )
}