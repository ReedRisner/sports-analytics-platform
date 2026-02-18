import { cn } from '@/lib/utils'
import { EDGE_COLORS, EDGE_THRESHOLDS } from '@/lib/constants'

interface EdgeIndicatorProps {
  edge: number
  recommendation: 'OVER' | 'UNDER' | 'PASS'
  className?: string
}

/**
 * Edge percentage indicator with color coding
 * - Strong edge (>10%): Bright green/red
 * - Moderate edge (5-10%): Medium green/red
 * - Weak edge (3-5%): Dim green/red
 * - Pass (<3%): Gray
 */
export function EdgeIndicator({ edge, recommendation, className }: EdgeIndicatorProps) {
  const getColorClass = () => {
    if (recommendation === 'PASS') {
      return EDGE_COLORS.pass
    }
    
    const absEdge = Math.abs(edge)
    
    if (absEdge >= EDGE_THRESHOLDS.strong) {
      return recommendation === 'OVER' 
        ? EDGE_COLORS.strong.over 
        : EDGE_COLORS.strong.under
    }
    
    if (absEdge >= EDGE_THRESHOLDS.moderate) {
      return recommendation === 'OVER'
        ? EDGE_COLORS.moderate.over
        : EDGE_COLORS.moderate.under
    }
    
    return EDGE_COLORS.weak
  }

  return (
    <div
      className={cn(
        'inline-flex items-center justify-center px-3 py-1.5 rounded-md border font-mono text-sm font-medium',
        getColorClass(),
        className
      )}
    >
      {edge > 0 ? '+' : ''}{edge.toFixed(1)}%
    </div>
  )
}
