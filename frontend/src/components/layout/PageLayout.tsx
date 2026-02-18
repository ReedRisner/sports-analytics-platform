import { Outlet } from 'react-router-dom'
import { Header } from "./Header"

/**
 * Main page layout wrapper
 * Includes header and content area
 */
export function PageLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}