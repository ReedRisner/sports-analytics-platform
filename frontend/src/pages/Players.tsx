import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { playersAPI } from '@/api/endpoints/players'
import { useNavigate } from 'react-router-dom'
import { Search, User } from 'lucide-react'

/**
 * Players page - Search and browse all players
 */
export default function Players() {
  const [searchQuery, setSearchQuery] = useState('')
  const navigate = useNavigate()

  // Fetch players based on search query
  const { data: players, isLoading } = useQuery({
    queryKey: ['players-search', searchQuery],
    queryFn: () => playersAPI.search(searchQuery),
    enabled: searchQuery.length >= 2, // Only search when 2+ characters
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Players</h1>
        <p className="text-muted-foreground mt-2">
          Search for players and view their projections
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search players by name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-3 rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Searching...</p>
        </div>
      )}

      {/* Results Grid */}
      {!isLoading && players && players.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {players.map((player) => (
            <button
              key={player.id}
              onClick={() => navigate(`/player/${player.id}`)}
              className="group rounded-xl border border-border bg-card p-6 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 transition-all text-left"
            >
              <div className="flex items-center gap-4">
                {/* Player Photo */}
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center border-2 border-border group-hover:border-primary/50 transition-colors">
                  {player.photo_url ? (
                    <img
                      src={player.photo_url}
                      alt={player.name}
                      className="w-full h-full rounded-full object-cover"
                    />
                  ) : (
                    <User className="w-8 h-8 text-muted-foreground" />
                  )}
                </div>

                {/* Player Info */}
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-lg group-hover:text-primary transition-colors truncate">
                    {player.name}
                  </h3>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                    <span>#{player.jersey}</span>
                    <span>•</span>
                    <span>{player.position}</span>
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">
                    {player.team_name}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* No Results */}
      {!isLoading && players && players.length === 0 && searchQuery.length >= 2 && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">
            No players found matching "{searchQuery}"
          </p>
        </div>
      )}

      {/* Initial State - Just search prompt */}
      {!searchQuery && (
        <div className="text-center py-20">
          <Search className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <p className="text-lg text-muted-foreground mb-2">
            Search for any NBA player
          </p>
          <p className="text-sm text-muted-foreground">
            Start typing a name in the search bar above
          </p>
        </div>
      )}
    </div>
  )
}