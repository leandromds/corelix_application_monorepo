/**
 * Tests for useUpdateSession — PATCH /agenda/sessions/:id mutation.
 *
 * sonner is mocked at the top level so toast.success / toast.error
 * calls can be asserted without side effects in jsdom.
 */

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { renderHook, waitFor } from '@testing-library/react'
import { act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { toast } from 'sonner'
import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useUpdateSession } from './useUpdateSession'
import type { Session } from '../types'

// ---------------------------------------------------------------------------
// Fixtures
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

describe('useUpdateSession', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('chama PATCH /agenda/sessions/:id com o payload correto', async () => {
    let capturedBody: unknown = null
    let capturedId: string | undefined

    server.use(
      http.patch(
        BASE_URL + '/agenda/sessions/:id',
        async ({ request, params }) => {
          capturedId = params.id as string
          capturedBody = await request.json()
          return HttpResponse.json({ ...mockSession, status: 'completed' })
        },
      ),
    )

    const { result } = renderHook(() => useUpdateSession(), {
      wrapper: makeWrapper(),
    })

    act(() => {
      result.current.mutate({
        id: 'session-1',
        payload: { status: 'completed' },
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedId).toBe('session-1')
    expect(capturedBody).toMatchObject({ status: 'completed' })
  })

  it('dispara toast.success após atualizar sessão com sucesso', async () => {
    server.use(
      http.patch(BASE_URL + '/agenda/sessions/:id', () =>
        HttpResponse.json({ ...mockSession, status: 'completed' }),
      ),
    )

    const { result } = renderHook(() => useUpdateSession(), {
      wrapper: makeWrapper(),
    })

    act(() => {
      result.current.mutate({
        id: 'session-1',
        payload: { status: 'completed' },
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(toast.success).toHaveBeenCalledWith('Sessão atualizada')
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('dispara toast.error quando a atualização falha', async () => {
    server.use(
      http.patch(BASE_URL + '/agenda/sessions/:id', () =>
        HttpResponse.json({ detail: 'Not Found' }, { status: 404 }),
      ),
    )

    const { result } = renderHook(() => useUpdateSession(), {
      wrapper: makeWrapper(),
    })

    act(() => {
      result.current.mutate({
        id: 'session-999',
        payload: { status: 'completed' },
      })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(toast.error).toHaveBeenCalledWith('Erro ao atualizar sessão')
    expect(toast.success).not.toHaveBeenCalled()
  })
})
