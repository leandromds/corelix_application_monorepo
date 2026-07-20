import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import api from '@/services/api'
import type { HandoffResult } from '../types'

/**
 * Switch a conversation from AI mode to professional (handoff) mode.
 *
 * After a successful handoff the AI stops auto-replying and the conversation
 * appears in the professional's "waiting" queue.
 *
 * On success both query caches are invalidated so the list and thread refresh
 * automatically — no manual state updates needed.
 */
export function useHandoff() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (conversationId: string): Promise<HandoffResult> => {
      const { data } = await api.post<HandoffResult>(
        `/whatsapp/conversations/${conversationId}/handoff`,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['whatsapp-conversations'] })
      void queryClient.invalidateQueries({ queryKey: ['whatsapp-messages'] })
      toast.success('Conversa assumida com sucesso.')
    },
    onError: () => {
      toast.error('Erro ao assumir conversa.')
    },
  })
}
