import { http, HttpResponse } from 'msw'
import { renderHook, act, waitFor } from '@testing-library/react'
import { toast } from 'sonner'

import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useUpdateClient } from '@/features/clients/hooks/useUpdateClient'
import type { Client } from '@/features/clients/types'

// ---------------------------------------------------------------------------
// Hoist mock before any imports resolve
// ---------------------------------------------------------------------------

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CLIENT_ID = 'abc-123'

function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: CLIENT_ID,
    full_name: 'Ana Lima',
    phone: '+5511999999999',
    email: null,
    notes: null,
    is_active: true,
    whatsapp_opt_in: false,
    email_opt_in: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useUpdateClient', () => {
  it('chama PATCH /clients/:id com o payload correto', async () => {
    let receivedBody: unknown = null
    let capturedId: string | undefined

    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
      http.patch(BASE_URL + '/clients/:id', async ({ request, params }) => {
        capturedId = params['id'] as string
        receivedBody = await request.json()
        return HttpResponse.json(makeClient({ full_name: 'Ana Souza' }))
      }),
    )

    const { result } = renderHook(() => useUpdateClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate({ id: CLIENT_ID, payload: { full_name: 'Ana Souza' } })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedId).toBe(CLIENT_ID)
    expect(receivedBody).toMatchObject({ full_name: 'Ana Souza' })
  })

  it('dispara toast.success após atualização bem-sucedida', async () => {
    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
      http.patch(BASE_URL + '/clients/:id', () =>
        HttpResponse.json(makeClient({ full_name: 'Ana Souza' })),
      ),
    )

    const { result } = renderHook(() => useUpdateClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate({ id: CLIENT_ID, payload: { full_name: 'Ana Souza' } })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(toast.success).toHaveBeenCalledWith('Cliente atualizado')
  })

  it('dispara toast.error em caso de falha na atualização', async () => {
    server.use(
      http.patch(BASE_URL + '/clients/:id', () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    const { result } = renderHook(() => useUpdateClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate({ id: CLIENT_ID, payload: { full_name: 'Ana Souza' } })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(toast.error).toHaveBeenCalledWith('Erro ao atualizar cliente')
  })
})
