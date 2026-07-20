import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { ConversationWithMessages } from '../types'

/**
 * Fetch a single conversation with its full message history.
 *
 * The query is disabled when conversationId is null so no request is made
 * before the user selects a conversation — mirrors the `enabled` pattern
 * used across the codebase.
 */
export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ['whatsapp-messages', conversationId],
    queryFn: async () => {
      const { data } = await api.get<ConversationWithMessages>(
        `/whatsapp/conversations/${conversationId}`,
      )
      return data
    },
    enabled: !!conversationId,
  })
}
