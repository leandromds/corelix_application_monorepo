import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useUpcomingSessions } from './useUpcomingSessions'
import type { Session } from '../types'

const mockSession: Session = {
  id: 'session-1',
  client_id: 'client-1',
  client_name: 'Maria Costa',
  scheduled_at: new Date(Date.now() + 86_400_000).toISOString(), // tomorrow
  duration_minutes: 50,
  price: '200.00',
  status: 'scheduled',
  notes: null,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('useUpcomingSessions', () => {
  it('retorna lista de próximas sessões com sucesso', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions/upcoming', () =>
        HttpResponse.json([mockSession]),
      ),
    )

    const { result } = renderHook(() => useUpcomingSessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toHaveLength(1)
    expect(result.current.data![0].client_name).toBe('Maria Costa')
  })

  it('retorna lista vazia quando não há próximas sessões', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions/upcoming', () =>
        HttpResponse.json([]),
      ),
    )

    const { result } = renderHook(() => useUpcomingSessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(0)
  })

  it('expõe isError em caso de falha da API', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions/upcoming', () =>
        HttpResponse.error(),
      ),
    )

    const { result } = renderHook(() => useUpcomingSessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
