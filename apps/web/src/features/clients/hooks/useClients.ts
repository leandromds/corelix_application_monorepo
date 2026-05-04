import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { Client, ClientsListParams } from '../types'

export function useClients(params?: ClientsListParams) {
  return useQuery({
    queryKey: ['clients', params],
    queryFn: async () => {
      const { data } = await api.get<Client[]>('/clients', { params })
      return data
    },
  })
}
