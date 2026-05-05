import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/services/api'
import { useAuth } from '@/hooks/useAuth'
import type { ProfessionalResponse } from '@/types/auth'

// ---------------------------------------------------------------------------
// Payload type
// ---------------------------------------------------------------------------

/**
 * PATCH /professionals/me payload.
 *
 * The backend uses exclude_none=True, so null fields are dropped server-side
 * and the corresponding column stays unchanged.  Sending null is therefore
 * equivalent to "leave this field as-is" — it cannot be used to clear it.
 * This is a known limitation of the current backend (see ADR-024 trade-off).
 */
export interface UpdateProfilePayload {
  full_name?: string
  specialty?: string | null
  bio?: string | null
  phone?: string | null
  session_duration?: number
  session_price?: number
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useUpdateProfile() {
  const { refreshProfile } = useAuth()

  return useMutation({
    mutationFn: (payload: UpdateProfilePayload) =>
      api
        .patch<ProfessionalResponse>('/professionals/me', payload)
        .then((r) => r.data),

    onSuccess: async () => {
      // Re-fetch /professionals/me so the AuthContext stays in sync with
      // the newly saved values (Sidebar avatar, form default values, etc.)
      await refreshProfile()
      toast.success('Perfil atualizado')
    },

    onError: () => toast.error('Erro ao atualizar perfil'),
  })
}
