/**
 * useAuth -- convenience hook for consuming AuthContext.
 *
 * Throws a descriptive error if called outside of <AuthProvider>.
 * This catches misconfigured component trees at development time
 * rather than silently returning null/undefined values.
 */

import { useContext } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import type { ProfessionalResponse } from '@/types/auth'
import type { RegisterRequest } from '@/types/auth'

export interface UseAuthReturn {
  professional: ProfessionalResponse | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => Promise<void>
}

export function useAuth(): UseAuthReturn {
  const context = useContext(AuthContext)

  if (context === null) {
    throw new Error(
      'useAuth must be used within an <AuthProvider>. ' +
        'Make sure your component tree includes <AuthProvider> at the root.',
    )
  }

  return context
}
