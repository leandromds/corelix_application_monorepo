/**
 * ProtectedRoute — wraps routes that require authentication.
 *
 * Behaviour:
 * - isLoading=true  → render a spinner (prevents redirect flash during session restore)
 * - not authenticated → redirect to /login
 * - authenticated    → render children
 *
 * Why the spinner matters: on page refresh, AuthProvider attempts to restore
 * the session via the refresh_token cookie. This is async. Without the spinner,
 * the route guard would immediately see isAuthenticated=false and redirect to
 * /login — even though the user IS authenticated and the cookie is valid.
 */

import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div style={styles.center}>
        <div style={styles.spinner} aria-label="Carregando..." />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

const styles: Record<string, React.CSSProperties> = {
  center: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
  },
  spinner: {
    width: 36,
    height: 36,
    border: '3px solid #e5e7eb',
    borderTopColor: '#6366f1',
    borderRadius: '50%',
    animation: 'spin 0.7s linear infinite',
  },
}
