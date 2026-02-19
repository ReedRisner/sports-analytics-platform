import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface User {
  id: number
  email: string
  name: string
  tier: string
}

/**
 * Main header with navigation
 */
export function Header() {
  const location = useLocation()
  const navigate = useNavigate()

  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      setUser(JSON.parse(storedUser))
    }
  }, [location.pathname]) // re-check when route changes

  const isActive = (path: string) => {
    return location.pathname === path
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    navigate('/')
  }

  const navLinks = [
    { path: '/', label: 'Dashboard' },
    { path: '/edges', label: 'Edge Finder' },
    { path: '/players', label: 'Players' },
    { path: '/matchups', label: 'Matchups' },
    { path: '/pricing', label: 'Pricing' },
     { path: '/accuracy', label: 'Accuracy' },
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

        {/* Right Side */}
        <div className="flex items-center gap-4">
          {user ? (
            <>
              <span className="text-sm font-medium text-primary">
                {user.name}
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-muted-foreground hover:text-red-400 transition-colors"
              >
                Logout
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
            >
              Login
            </Link>
          )}
        </div>

      </div>
    </header>
  )
}
