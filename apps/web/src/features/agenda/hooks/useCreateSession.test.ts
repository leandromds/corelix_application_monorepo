/**
 * Tests for useCreateSession — POST /agenda/sessions mutation.
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
import { useCreateSession } from './useCreateSession'
import type { CreateSessionPayload, Session } from '../types'

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

const createPayload: CreateSessionPayload = {
  client_id: 'client-1',
  scheduled_at: '2025-07-21T10:00:00.000Z',
  duration_minutes: 50,
  price: '150.00',
  status: 'scheduled',
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useCreateSession', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('chama POST /agenda/sessions com o payload correto', async () => {
    let capturedBody: unknown = null

    server.use(
      http.post(BASE_URL + '/agenda/sessions', async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ ...mockSession }, { status: 201 })
      }),
    )

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: makeWrapper(),
    })

    act(() => {
      result.current.mutate(createPayload)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedBody).toMatchObject({
      client_id: 'client-1',
      duration_minutes: 50,
      price: '150.00',
      status: 'scheduled',
    })
  })

  it('dispara toast.success após criar sessão com sucesso', async () => {
    server.use(
      http.post(BASE_URL + '/agenda/sessions', () =>
        HttpResponse.json({ ...mockSession }, { status: 201 }),
      ),
    )

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: makeWrapper(),
    })

    act(() => {
      result.current.mutate(createPayload)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(toast.success).toHaveBeenCalledWith('Sessão agendada')
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('dispara toast.error quando a criação falha', async () => {
    server.use(
      http.post(BASE_URL + '/agenda/sessions', () =>
        HttpResponse.json({ detail: 'Unprocessable Entity' }, { status: 422 }),
      ),
    )

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: makeWrapper(),
    })

    act(() => {
      result.current.mutate(createPayload)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(toast.error).toHaveBeenCalledWith('Erro ao agendar sessão')
    expect(toast.success).not.toHaveBeenCalled()
  })
})
