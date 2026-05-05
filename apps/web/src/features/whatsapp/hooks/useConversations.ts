import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { Conversation } from '../types'

/**
 * Fetch the authenticated professional's WhatsApp conversations.
 *
 * @param statusFilter  Optional status filter: 'active' | 'resolved' | 'waiting_professional'
 *                      When omitted the backend returns all statuses.
 */
export function useConversations(statusFilter?: string) {
  return useQuery({
    queryKey: ['whatsapp-conversations', statusFilter],
    queryFn: async () => {
      const params = statusFilter ? { status: statusFilter } : undefined
      const { data } = await api.get<Conversation[]>('/whatsapp/conversations', { params })
      return data
    },
  })
}
