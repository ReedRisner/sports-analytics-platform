import { ReactNode } from 'react'

interface TooltipProps {
  children: ReactNode
  content: string
}

export function InfoTooltip({ children, content }: TooltipProps) {
  return (
    <span className="group relative inline-flex items-center">
      <span className="border-b border-dotted border-muted-foreground cursor-help">
        {children}
      </span>
      <span className="invisible group-hover:visible absolute left-0 bottom-full mb-2 w-64 p-3 bg-gray-900 text-white text-sm rounded-lg shadow-xl border border-gray-700 z-50">
        {content}
        <span className="absolute left-4 top-full w-0 h-0 border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-gray-900" />
      </span>
    </span>
  )
}