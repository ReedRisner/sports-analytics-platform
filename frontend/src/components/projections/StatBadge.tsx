import { cn } from '@/lib/utils'
import { STAT_COLORS } from '@/lib/constants'

interface StatBadgeProps {
  statType: string
  className?: string
}

/**
 * Stat type badge with color coding
 */
export function StatBadge({ statType, className }: StatBadgeProps) {
  const color = STAT_COLORS[statType.toLowerCase()] || 'text-foreground'
  
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-1 rounded text-xs font-medium uppercase',
        color,
        className
      )}
    >
      {statType}
    </span>
  )
}
