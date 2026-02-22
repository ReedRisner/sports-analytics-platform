import { useQuery } from '@tanstack/react-query'
import { oddsAPI } from '@/api/endpoints/odds'

/**
 * Hook to fetch edge finder data
 */
export function useEdgeFinder(
  statType?: string,
  sportsbook?: string,
  minEdgePct: number = 3.0,
  position?: string
) {
  return useQuery({
    queryKey: ['edges', statType, sportsbook, minEdgePct, position],
    queryFn: () => oddsAPI.getEdgeFinder(statType, sportsbook, minEdgePct, position),
    refetchInterval: 180000, // Refetch every 3 minutes
    staleTime: 180000, // Consider data stale after 3 minutes
  })
}
