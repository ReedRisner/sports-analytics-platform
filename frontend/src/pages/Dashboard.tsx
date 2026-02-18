/**
 * Dashboard - Today's top edges
 */
export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-2">
          Today's top prop betting edges
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {/* Stats cards */}
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="text-sm text-muted-foreground">Total Edges</div>
          <div className="text-3xl font-bold mt-2">--</div>
        </div>
        
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="text-sm text-muted-foreground">Avg Edge %</div>
          <div className="text-3xl font-bold mt-2">--</div>
        </div>
        
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="text-sm text-muted-foreground">High Confidence</div>
          <div className="text-3xl font-bold mt-2">--</div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-xl font-semibold mb-4">Top Edges Today</h2>
        <p className="text-muted-foreground text-sm">
          Connect to backend to see real projections...
        </p>
      </div>
    </div>
  )
}