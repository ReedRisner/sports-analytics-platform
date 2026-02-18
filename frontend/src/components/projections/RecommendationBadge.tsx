import { cn } from '@/lib/utils'

interface RecommendationBadgeProps {
  recommendation: 'OVER' | 'UNDER' | 'PASS'
  className?: string
}

/**
 * Recommendation badge (OVER/UNDER/PASS)
 */
export function RecommendationBadge({ recommendation, className }: RecommendationBadgeProps) {
  const getColorClass = () => {
    switch (recommendation) {
      case 'OVER':
        return 'bg-green-500/20 text-green-400 border-green-500'
      case 'UNDER':
        return 'bg-red-500/20 text-red-400 border-red-500'
      case 'PASS':
        return 'bg-gray-500/20 text-gray-400 border-gray-500'
    }
  }

  return (
    <div
      className={cn(
        'inline-flex items-center px-2.5 py-1 rounded-md border text-xs font-semibold',
        getColorClass(),
        className
      )}
    >
      {recommendation}
    </div>
  )
}
