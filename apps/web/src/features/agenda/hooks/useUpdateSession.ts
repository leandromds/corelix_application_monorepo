import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/services/api'
import type { UpdateSessionPayload, Session } from '../types'

export function useUpdateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string
      payload: UpdateSessionPayload
    }) =>
      api
        .patch<Session>(`/agenda/sessions/${id}`, payload)
        .then((r) => r.data),
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['sessions'] })
      void queryClient.invalidateQueries({ queryKey: ['sessions', id] })
      toast.success('Sessão atualizada')
    },
    onError: () => toast.error('Erro ao atualizar sessão'),
  })
}
