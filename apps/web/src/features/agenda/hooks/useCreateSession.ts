import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/services/api'
import type { CreateSessionPayload, Session } from '../types'

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateSessionPayload) =>
      api.post<Session>('/agenda/sessions', payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['sessions'] })
      toast.success('Sessão agendada')
    },
    onError: () => toast.error('Erro ao agendar sessão'),
  })
}
