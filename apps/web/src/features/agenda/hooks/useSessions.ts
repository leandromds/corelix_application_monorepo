import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { Session, SessionsListParams } from '../types'

export function useSessions(params?: SessionsListParams) {
  return useQuery({
    queryKey: ['sessions', params],
    queryFn: async () => {
      const { data } = await api.get<Session[]>('/agenda/sessions', { params })
      return data
    },
  })
}
