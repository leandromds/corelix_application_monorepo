import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { Session } from '../types'

export function useUpcomingSessions() {
  return useQuery({
    queryKey: ['sessions', 'upcoming'],
    queryFn: async () => {
      const { data } = await api.get<Session[]>('/agenda/sessions/upcoming')
      return data
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}
