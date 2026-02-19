import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, TrendingUp, Clock, Activity, Shield, Zap, Target } from 'lucide-react'

interface Team {
  id: number
  name: string
  abbreviation: string
  record: string
  pace?: number
  offensive_rating?: number
  defensive_rating?: number
  points_per_game?: number
  opp_points_per_game?: number
}

interface Game {
  id: number
  date: string
  status: string
  home_score: number | null
  away_score: number | null
  home_team: Team
  away_team: Team
  spread?: {
    home_spread: number
    away_spread: number
    odds: number
  }
  total?: {
    over_under: number
    over_odds: number
    under_odds: number
  }
}

interface GamesResponse {
  date: string
  games: Game[]
  count: number
}

interface GameBet {
  player_id: number
  player_name: string
  team_abbr: string
  position: string
  stat_type: string
  line: number
  projected: number
  edge_pct: number
  over_prob: number
  under_prob: number
  recommendation: 'OVER' | 'UNDER'
  matchup_grade?: string
}

interface GameBetsResponse {
  game_id: number
  count: number
  bets: GameBet[]
}

export default function MatchupsPage() {
  const [selectedGame, setSelectedGame] = useState<number | null>(null)
  const navigate = useNavigate()

  // Fetch today's games
  const { data: gamesResponse, isLoading: gamesLoading } = useQuery<GamesResponse>({
    queryKey: ['todays-games'],
    queryFn: async () => {
      const { data } = await apiClient.get<GamesResponse>('/games/today?stat_types=points')
      return data
    },
  })

  const games = gamesResponse?.games || []

  // Fetch best bets for selected game
  const { data: gameBetsResponse, isLoading: betsLoading } = useQuery<GameBetsResponse>({
    queryKey: ['game-bets', selectedGame],
    queryFn: async () => {
      if (!selectedGame) return { game_id: 0, count: 0, bets: [] }
      const { data } = await apiClient.get<GameBetsResponse>(`/games/${selectedGame}/best-bets`)
      return data
    },
    enabled: !!selectedGame,
  })

  const gameBets = gameBetsResponse?.bets || []
  const selectedGameData = games?.find((g: Game) => g.id === selectedGame)

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-primary/5 to-background p-8">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-transparent to-primary/20 blur-2xl" />
        
        <div className="relative">
          <h1 className="text-5xl font-black tracking-tight mb-2">
            Today's Matchups
          </h1>
          <p className="text-muted-foreground text-lg">
            Game spreads and top betting opportunities
          </p>
        </div>
      </div>

      {/* Loading State */}
      {gamesLoading && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading today's games...</p>
        </div>
      )}

      {/* No Games */}
      {!gamesLoading && (!games || games.length === 0) && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <Clock className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-xl font-bold mb-2">No Games Today</h3>
          <p className="text-muted-foreground">Check back on game day!</p>
        </div>
      )}

      {/* Games Grid */}
      {!selectedGame && games && games.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {games.map((game: Game) => (
            <button
              key={game.id}
              onClick={() => setSelectedGame(game.id)}
              className="group rounded-xl border border-border bg-card hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 transition-all p-6 text-left"
            >
              {/* Game Time */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  <span>{game.date || 'TBD'}</span>
                </div>
                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>

              {/* Away Team */}
              <div className="flex items-center justify-between mb-3 pb-3 border-b border-border/50">
                <div>
                  <div className="font-bold text-lg">{game.away_team.abbreviation}</div>
                  <div className="text-sm text-muted-foreground">{game.away_team.record}</div>
                </div>
                {game.spread && (
                  <div className="text-right">
                    <div className="font-mono font-semibold">
                      {game.spread.away_spread > 0 ? '+' : ''}{game.spread.away_spread}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      ({game.spread.odds > 0 ? '+' : ''}{game.spread.odds})
                    </div>
                  </div>
                )}
              </div>

              {/* Home Team */}
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="font-bold text-lg">{game.home_team.abbreviation}</div>
                  <div className="text-sm text-muted-foreground">{game.home_team.record}</div>
                </div>
                {game.spread && (
                  <div className="text-right">
                    <div className="font-mono font-semibold">
                      {game.spread.home_spread > 0 ? '+' : ''}{game.spread.home_spread}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      ({game.spread.odds > 0 ? '+' : ''}{game.spread.odds})
                    </div>
                  </div>
                )}
              </div>

              {/* Over/Under */}
              {game.total && (
                <div className="pt-3 border-t border-border/50">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">O/U</span>
                    <span className="font-mono font-semibold">{game.total.over_under}</span>
                  </div>
                </div>
              )}

              {/* Status Badge */}
              {game.status === 'live' && (
                <div className="mt-3 pt-3 border-t border-border/50">
                  <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-bold">
                    <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                    LIVE
                  </div>
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Selected Game Detail View */}
      {selectedGame && selectedGameData && (
        <div className="space-y-6">
          {/* Back Button */}
          <button
            onClick={() => setSelectedGame(null)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
            Back to all games
          </button>

          {/* Game Header */}
          <div className="rounded-xl border border-border bg-card p-8">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="w-4 h-4" />
                <span>{selectedGameData.date || 'TBD'}</span>
              </div>
              {selectedGameData.status === 'live' && (
                <div className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-bold">
                  <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                  LIVE
                </div>
              )}
            </div>

            {/* Teams */}
            <div className="grid grid-cols-2 gap-8 mb-6">
              {/* Away Team */}
              <div className="text-center">
                <div className="text-3xl font-black mb-2">{selectedGameData.away_team.abbreviation}</div>
                <div className="text-sm text-muted-foreground mb-3">{selectedGameData.away_team.name}</div>
                <div className="text-lg font-semibold">{selectedGameData.away_team.record}</div>
              </div>

              {/* VS */}
              <div className="text-center flex items-center justify-center">
                <div className="text-2xl font-bold text-muted-foreground">@</div>
              </div>

              {/* Home Team */}
              <div className="text-center">
                <div className="text-3xl font-black mb-2">{selectedGameData.home_team.abbreviation}</div>
                <div className="text-sm text-muted-foreground mb-3">{selectedGameData.home_team.name}</div>
                <div className="text-lg font-semibold">{selectedGameData.home_team.record}</div>
              </div>
            </div>

            {/* Game Lines */}
            <div className="pt-6 border-t border-border">
              <div className="text-sm text-muted-foreground mb-4 text-center">Game Lines</div>
              <div className="grid grid-cols-2 gap-4">
                {selectedGameData.spread ? (
                  <div className="text-center">
                    <div className="text-sm text-muted-foreground mb-2">Spread</div>
                    <div className="font-mono font-bold text-lg">
                      {selectedGameData.home_team.abbreviation} {selectedGameData.spread.home_spread > 0 ? '+' : ''}{selectedGameData.spread.home_spread}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      ({selectedGameData.spread.odds > 0 ? '+' : ''}{selectedGameData.spread.odds})
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <div className="text-sm text-muted-foreground mb-2">Spread</div>
                    <div className="text-sm text-muted-foreground">N/A</div>
                  </div>
                )}
                {selectedGameData.total ? (
                  <div className="text-center">
                    <div className="text-sm text-muted-foreground mb-2">Total</div>
                    <div className="font-mono font-bold text-lg">
                      O/U {selectedGameData.total.over_under}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      O: {selectedGameData.total.over_odds} / U: {selectedGameData.total.under_odds}
                    </div>
                  </div>
                ) : (
                  <div className="text-center">
                    <div className="text-sm text-muted-foreground mb-2">Total</div>
                    <div className="text-sm text-muted-foreground">N/A</div>
                  </div>
                )}
              </div>
              <p className="text-xs text-muted-foreground text-center mt-4">
                💡 Game lines require odds data in database
              </p>
            </div>
          </div>

          {/* Team Stats Comparison */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary" />
              Team Stats Comparison
            </h2>

            <div className="space-y-6">
              {/* Offensive Rating */}
              <div>
                <div className="flex items-center gap-2 text-sm mb-3">
                  <Target className="w-4 h-4 text-green-400" />
                  <span className="font-medium">Offensive Rating</span>
                </div>
                <div className="grid grid-cols-3 gap-4 items-center">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-400">
                      {selectedGameData.away_team.offensive_rating?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.away_team.abbreviation}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-muted-foreground">VS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-400">
                      {selectedGameData.home_team.offensive_rating?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.home_team.abbreviation}</div>
                  </div>
                </div>
              </div>

              {/* Defensive Rating */}
              <div>
                <div className="flex items-center gap-2 text-sm mb-3">
                  <Shield className="w-4 h-4 text-blue-400" />
                  <span className="font-medium">Defensive Rating</span>
                </div>
                <div className="grid grid-cols-3 gap-4 items-center">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-400">
                      {selectedGameData.away_team.defensive_rating?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.away_team.abbreviation}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-muted-foreground">VS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-400">
                      {selectedGameData.home_team.defensive_rating?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.home_team.abbreviation}</div>
                  </div>
                </div>
              </div>

              {/* Pace */}
              <div>
                <div className="flex items-center gap-2 text-sm mb-3">
                  <Zap className="w-4 h-4 text-yellow-400" />
                  <span className="font-medium">Pace (Possessions/Game)</span>
                </div>
                <div className="grid grid-cols-3 gap-4 items-center">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-yellow-400">
                      {selectedGameData.away_team.pace?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.away_team.abbreviation}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-muted-foreground">VS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-yellow-400">
                      {selectedGameData.home_team.pace?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.home_team.abbreviation}</div>
                  </div>
                </div>
              </div>

              {/* Points Per Game */}
              <div>
                <div className="flex items-center gap-2 text-sm mb-3">
                  <Activity className="w-4 h-4 text-orange-400" />
                  <span className="font-medium">Points Per Game</span>
                </div>
                <div className="grid grid-cols-3 gap-4 items-center">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-400">
                      {selectedGameData.away_team.points_per_game?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.away_team.abbreviation}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-muted-foreground">VS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-400">
                      {selectedGameData.home_team.points_per_game?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.home_team.abbreviation}</div>
                  </div>
                </div>
              </div>

              {/* Points Allowed */}
              <div>
                <div className="flex items-center gap-2 text-sm mb-3">
                  <Shield className="w-4 h-4 text-red-400" />
                  <span className="font-medium">Opp Points Per Game</span>
                </div>
                <div className="grid grid-cols-3 gap-4 items-center">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-400">
                      {selectedGameData.away_team.opp_points_per_game?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.away_team.abbreviation}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-muted-foreground">VS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-400">
                      {selectedGameData.home_team.opp_points_per_game?.toFixed(1) || 'N/A'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">{selectedGameData.home_team.abbreviation}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Best Bets for This Game */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-primary" />
              Top 5 Player Props
            </h2>

            {betsLoading && (
              <div className="text-center py-12">
                <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-muted-foreground">Loading best bets...</p>
              </div>
            )}

            {!betsLoading && (!gameBets || gameBets.length === 0) && (
              <div className="text-center py-12">
                <TrendingUp className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No bets available for this game</p>
              </div>
            )}

            {!betsLoading && gameBets && gameBets.length > 0 && (
              <div className="space-y-3">
                {gameBets.slice(0, 5).map((bet: GameBet, index: number) => (
                  <button
                    key={`${bet.player_id}-${bet.stat_type}`}
                    onClick={() => navigate(`/player/${bet.player_id}`)}
                    className="w-full rounded-lg border border-border bg-background p-4 hover:border-primary/50 hover:shadow-lg transition-all text-left group cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      {/* Rank */}
                      <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/50 flex items-center justify-center shrink-0">
                        <span className="text-xs font-bold text-primary">#{index + 1}</span>
                      </div>

                      {/* Player Info */}
                      <div className="flex-1 ml-4">
                        <div className="font-bold group-hover:text-primary transition-colors">{bet.player_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {bet.team_abbr} • {bet.position}
                        </div>
                      </div>

                      {/* Bet Info */}
                      <div className="text-right mr-4">
                        <div className={`text-lg font-bold ${
                          bet.recommendation === 'OVER' ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {bet.recommendation} {bet.line}
                        </div>
                        <div className="text-xs text-muted-foreground uppercase">
                          {bet.stat_type}
                        </div>
                      </div>

                      {/* Edge */}
                      <div className="text-right">
                        <div className="text-lg font-bold font-mono text-primary">
                          +{bet.edge_pct.toFixed(1)}%
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {bet.recommendation === 'OVER' 
                            ? `${bet.over_prob.toFixed(0)}%`
                            : `${bet.under_prob.toFixed(0)}%`
                          } win
                        </div>
                      </div>

                      {/* Hover Arrow */}
                      <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors opacity-0 group-hover:opacity-100 ml-2" />
                    </div>

                    {/* Projection Bar */}
                    <div className="mt-3 pt-3 border-t border-border/50">
                      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                        <span>Projected: {bet.projected.toFixed(1)}</span>
                        <span>Line: {bet.line}</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full ${
                            bet.recommendation === 'OVER' ? 'bg-green-500' : 'bg-red-500'
                          }`}
                          style={{ 
                            width: `${Math.min((bet.projected / bet.line) * 100, 100)}%` 
                          }}
                        />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}