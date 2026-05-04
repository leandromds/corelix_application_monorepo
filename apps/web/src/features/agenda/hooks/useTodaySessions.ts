import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { Session } from '../types'

export function useTodaySessions() {
  return useQuery({
    queryKey: ['sessions', 'today'],
    queryFn: async () => {
      const { data } = await api.get<Session[]>('/agenda/sessions/today')
      return data
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
