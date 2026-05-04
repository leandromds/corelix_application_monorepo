import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/services/api'
import type { Client, UpdateClientPayload } from '../types'

export function useUpdateClient() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateClientPayload }) =>
      api.patch<Client>(`/clients/${id}`, payload).then((r) => r.data),
    onSuccess: (_, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['clients'] })
      void queryClient.invalidateQueries({ queryKey: ['clients', id] })
      toast.success('Cliente atualizado')
    },
    onError: () => toast.error('Erro ao atualizar cliente'),
  })
}
