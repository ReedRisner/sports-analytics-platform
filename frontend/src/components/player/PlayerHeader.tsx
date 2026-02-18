import { Player } from '@/api/types'
import { User } from 'lucide-react'

interface PlayerHeaderProps {
  player: Player
}

/**
 * Player header with photo, name, team, position
 */
export function PlayerHeader({ player }: PlayerHeaderProps) {
  return (
    <div className="rounded-xl border border-border bg-gradient-to-br from-card to-card/50 p-6">
      <div className="flex items-center gap-6">
        {/* Player Photo */}
        <div className="w-24 h-24 rounded-full bg-muted flex items-center justify-center border-2 border-primary/20">
          {player.photo_url ? (
            <img
              src={player.photo_url}
              alt={player.name}
              className="w-full h-full rounded-full object-cover"
            />
          ) : (
            <User className="w-12 h-12 text-muted-foreground" />
          )}
        </div>

        {/* Player Info */}
        <div className="flex-1">
          <h1 className="text-4xl font-bold mb-2">{player.name}</h1>
          <div className="flex items-center gap-4 text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="text-sm">#{player.jersey}</span>
              <span className="text-sm">•</span>
              <span className="text-sm font-medium">{player.position}</span>
            </div>
            <span className="text-sm">•</span>
            <div className="text-sm font-medium">{player.team_name}</div>
          </div>
          {player.height && player.weight && (
            <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
              <span>{player.height}</span>
              <span>•</span>
              <span>{player.weight} lbs</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
