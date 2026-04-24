/**
 * PublicRoute — wraps routes that should NOT be accessible when authenticated.
 *
 * Behaviour:
 * - isLoading=true  → render null (wait for session restore before deciding)
 * - authenticated   → redirect to /dashboard
 * - not authenticated → render children (login page, register page)
 */

import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

interface PublicRouteProps {
  children: React.ReactNode
}

export function PublicRoute({ children }: PublicRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()

  // Wait silently — avoids flickering the login page before the
  // session restore check completes.
  if (isLoading) return null

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
