import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'
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
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  useEffect(() => {
    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      setUser(JSON.parse(storedUser))
    }
    setIsMobileMenuOpen(false)
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
    { path: '/bets', label: 'Bets' },
    { path: '/pricing', label: 'Pricing' },
     { path: '/accuracy', label: 'Accuracy' },
  ]

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container mx-auto px-4 min-h-16 py-3 md:py-0 flex flex-wrap items-center justify-between gap-3">
        
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
        <div className="hidden md:flex items-center gap-4">
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

        {/* Mobile Menu Trigger */}
        <button
          type="button"
          className="md:hidden inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:text-primary hover:bg-muted transition-colors"
          onClick={() => setIsMobileMenuOpen((prev) => !prev)}
          aria-label={isMobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={isMobileMenuOpen}
        >
          {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

        {isMobileMenuOpen && (
          <div className="w-full md:hidden border-t border-border pt-3 pb-1 space-y-2">
            <nav className="flex flex-col gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className={cn(
                    'rounded-md px-2 py-2 text-sm font-medium transition-colors hover:text-primary hover:bg-muted',
                    isActive(link.path)
                      ? 'text-primary bg-muted/50'
                      : 'text-muted-foreground'
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            <div className="pt-1 border-t border-border">
              {user ? (
                <div className="flex items-center justify-between px-2 py-2">
                  <span className="text-sm font-medium text-primary">{user.name}</span>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-muted-foreground hover:text-red-400 transition-colors"
                  >
                    Logout
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="block rounded-md px-2 py-2 text-sm font-medium text-muted-foreground hover:text-primary hover:bg-muted transition-colors"
                >
                  Login
                </Link>
              )}
            </div>
          </div>
        )}

      </div>
    </header>
  )
}
