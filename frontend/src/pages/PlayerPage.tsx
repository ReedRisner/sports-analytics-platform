import { useParams } from 'react-router-dom'

/**
 * Player Page - Deep dive into player projections
 */
export default function PlayerPage() {
  const { id } = useParams<{ id: string }>()
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Player #{id}</h1>
        <p className="text-muted-foreground mt-2">
          Detailed projections and matchup analysis
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Projection</h2>
          <p className="text-muted-foreground text-sm">
            Projection card coming soon...
          </p>
        </div>
        
        <div className="rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Matchup</h2>
          <p className="text-muted-foreground text-sm">
            Opponent breakdown coming soon...
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Game Log</h2>
        <p className="text-muted-foreground text-sm">
          Chart coming soon...
        </p>
      </div>
    </div>
  )
}