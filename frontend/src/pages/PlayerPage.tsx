import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { playersAPI } from '@/api/endpoints/players'
import { projectionsAPI } from '@/api/endpoints/projections'
import { oddsAPI } from '@/api/endpoints/odds'
import { STAT_TYPES } from '@/lib/constants'
import { PlayerHeader } from '@/components/player/PlayerHeader'
import { ProjectionCard } from '@/components/player/ProjectionCard'
import { OpponentBreakdown } from '@/components/player/OpponentBreakdown'
import { GameLogChart } from '@/components/player/GameLogChart'
import { StatsBreakdown } from '@/components/player/StatsBreakdown'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

/**
 * Player Page - Deep dive into player projections and stats
 */
export default function PlayerPage() {
  const { id } = useParams<{ id: string }>()
  const playerId = parseInt(id || '0')
  const navigate = useNavigate()
  
  const [selectedStat, setSelectedStat] = useState<string>('points')
  const [gameLogFilter, setGameLogFilter] = useState<'l5' | 'l10' | 'season'>('l10')

  // Fetch player profile
  const { data: player, isLoading: playerLoading } = useQuery({
    queryKey: ['player', playerId],
    queryFn: () => playersAPI.getProfile(playerId),
    enabled: !!playerId,
  })

  // Fetch all projections for this player
  const { data: allProjections, isLoading: projectionsLoading } = useQuery({
    queryKey: ['player-projections', playerId],
    queryFn: () => projectionsAPI.getAllPlayerProjections(playerId),
    enabled: !!playerId,
  })

  // Fetch player odds (all stat types)
  const { data: playerOddsData } = useQuery({
    queryKey: ['player-odds', playerId],
    queryFn: () => oddsAPI.getPlayerOdds(playerId),
    enabled: !!playerId,
  })

  // Fetch game log
  const { data: gameLog } = useQuery({
    queryKey: ['player-gamelog', playerId],
    queryFn: () => playersAPI.getGameLog(playerId, 20), // Last 20 games
    enabled: !!playerId,
  })

  const isLoading = playerLoading || projectionsLoading

  // Get current projection for selected stat
  const currentProjection = allProjections?.find(p => p.stat_type === selectedStat)
  
  // Get current odds line for selected stat
  // Handle both possible response structures
  const playerOddsLines = Array.isArray(playerOddsData) 
    ? playerOddsData 
    : (playerOddsData as any)?.lines || []
  
  const currentOdds = playerOddsLines.find(
    (line: any) => line.stat_type === selectedStat && line.sportsbook === 'fanduel'
  )

  // Filter game log based on selection
  const filteredGameLog = gameLog ? (() => {
    switch (gameLogFilter) {
      case 'l5':
        return gameLog.slice(0, 5)
      case 'l10':
        return gameLog.slice(0, 10)
      case 'season':
        return gameLog
      default:
        return gameLog.slice(0, 10)
    }
  })() : []

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-muted-foreground">Loading player data...</p>
        </div>
      </div>
    )
  }

  if (!player) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">Player not found</h2>
          <p className="text-muted-foreground">The requested player could not be found.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Back Button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      {/* Player Header */}
      <PlayerHeader player={player} />

      {/* Stat Type Selector */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {Object.entries(STAT_TYPES).map(([value, label]) => (
          <button
            key={value}
            onClick={() => setSelectedStat(value)}
            className={`px-4 py-2 rounded-lg border whitespace-nowrap transition-colors ${
              selectedStat === value
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border hover:border-primary/50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Projection */}
        <div className="lg:col-span-1">
          <ProjectionCard
            projection={currentProjection}
            odds={currentOdds}
            statType={selectedStat}
          />
        </div>

        {/* Right Column - Opponent */}
        <div className="lg:col-span-2">
          <OpponentBreakdown
            matchup={currentProjection?.matchup}
            statType={selectedStat}
          />
        </div>
      </div>

      {/* Game Log Chart */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Performance History</h2>
          <div className="flex gap-2">
            {(['l5', 'l10', 'season'] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setGameLogFilter(filter)}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  gameLogFilter === filter
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted hover:bg-muted/80'
                }`}
              >
                {filter === 'l5' ? 'Last 5' : filter === 'l10' ? 'Last 10' : 'Season'}
              </button>
            ))}
          </div>
        </div>

        {gameLog && currentOdds ? (
          <GameLogChart
            games={filteredGameLog}
            statType={selectedStat}
            line={currentOdds.line}
          />
        ) : (
          <div className="text-center py-12 text-muted-foreground">
            No game log data available
          </div>
        )}
      </div>

      {/* Stats Breakdown */}
      <StatsBreakdown
        projection={currentProjection}
        gameLog={gameLog}
        statType={selectedStat}
      />
    </div>
  )
}