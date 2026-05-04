/**
 * Tests for useSessions — TanStack Query wrapper for GET /agenda/sessions.
 */

import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useSessions } from './useSessions'
import type { Session } from '../types'

// ---------------------------------------------------------------------------
// Shared fixture
// ---------------------------------------------------------------------------

const mockSession: Session = {
  id: 'session-1',
  client_id: 'client-1',
  client_name: 'Ana Lima',
  scheduled_at: '2025-07-21T10:00:00.000Z',
  duration_minutes: 50,
  price: '150.00',
  status: 'scheduled',
  notes: null,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useSessions', () => {
  it('retorna lista de sessões do servidor', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions', () =>
        HttpResponse.json([mockSession]),
      ),
    )

    const { result } = renderHook(() => useSessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toHaveLength(1)
    expect(result.current.data?.[0].id).toBe('session-1')
    expect(result.current.data?.[0].client_name).toBe('Ana Lima')
  })

  it('passa parâmetros date e limit na query string', async () => {
    let capturedUrl: URL | null = null

    server.use(
      http.get(BASE_URL + '/agenda/sessions', ({ request }) => {
        capturedUrl = new URL(request.url)
        return HttpResponse.json([mockSession])
      }),
    )

    const { result } = renderHook(
      () => useSessions({ date: '2025-07', limit: 100 }),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedUrl).not.toBeNull()
    expect(capturedUrl!.searchParams.get('date')).toBe('2025-07')
    expect(capturedUrl!.searchParams.get('limit')).toBe('100')
  })

  it('expõe isError quando o servidor retorna erro', async () => {
    server.use(
      http.get(BASE_URL + '/agenda/sessions', () =>
        HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 }),
      ),
    )

    const { result } = renderHook(() => useSessions(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})
