import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

/**
 * Main header with navigation
 */
export function Header() {
  const location = useLocation()
  
  const isActive = (path: string) => {
    return location.pathname === path
  }
  
  const navLinks = [
    { path: '/', label: 'Dashboard' },
    { path: '/edges', label: 'Edge Finder' },
    { path: '/players', label: 'Players' },
    { path: '/matchups', label: 'Matchups' },
    { path: '/pricing', label: 'Pricing' },
  ]
  
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <div className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            PropEdge
          </div>
          <div className="text-xs text-muted-foreground font-mono">BETA</div>
        </Link>
        
        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-6">
          {navLinks.map((link) => (
            <Link
              key={link.path}
              to={link.path}
              className={cn(
                'text-sm font-medium transition-colors hover:text-primary',
                isActive(link.path)
                  ? 'text-primary'
                  : 'text-muted-foreground'
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        
        {/* Login */}
        <div className="flex items-center gap-4">
          <Link
            to="/login"
            className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
          >
            Login
          </Link>
        </div>
      </div>
    </header>
  )
}