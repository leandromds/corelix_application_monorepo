import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useTodaySessions } from './useTodaySessions'
import type { Session } from '../types'

const mockSession: Session = {
  id: 'session-1',
  client_id: 'client-1',
  client_name: 'Ana Lima',
  scheduled_at: new Date().toISOString(),
  duration_minutes: 50,
  price: '150.00',
  status: 'scheduled',
  notes: null,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('useTodaySessions', () => {
  it('retorna lista de sessões de hoje com sucesso', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions/today', () =>
        HttpResponse.json([mockSession]),
      ),
    )

    const { result } = renderHook(() => useTodaySessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toHaveLength(1)
    expect(result.current.data![0].client_name).toBe('Ana Lima')
  })

  it('retorna lista vazia quando não há sessões hoje', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions/today', () =>
        HttpResponse.json([]),
      ),
    )

    const { result } = renderHook(() => useTodaySessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(0)
  })

  it('expõe isError em caso de falha da API', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions/today', () =>
        HttpResponse.error(),
      ),
    )

    const { result } = renderHook(() => useTodaySessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
