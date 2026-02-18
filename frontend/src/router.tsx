import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { PageLayout } from './components/layout/PageLayout'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'))
const EdgeFinder = lazy(() => import('./pages/Edgefinder'))
const PlayerPage = lazy(() => import('./pages/PlayerPage'))
const Players = lazy(() => import('./pages/Players'))
const MatchupRankings = lazy(() => import('./pages/MatchupRankings'))
const AuthPage = lazy(() => import('./pages/AuthPage'))
const Pricing = lazy(() => import('./pages/Pricing'))

// Loading fallback
const LoadingFallback = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="text-muted-foreground">Loading...</div>
  </div>
)

export function AppRouter() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="/" element={<PageLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="edges" element={<EdgeFinder />} />
          <Route path="players" element={<Players />} />
          <Route path="player/:id" element={<PlayerPage />} />
          <Route path="matchups" element={<MatchupRankings />} />
          <Route path="pricing" element={<Pricing />} />
          <Route path="*" element={<Navigate to="/" replace />} />
          <Route path="/auth" element={<AuthPage />} />
          
        </Route>
      </Routes>
    </Suspense>
  )
}