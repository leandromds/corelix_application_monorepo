import { http, HttpResponse } from 'msw'
import { renderHook, act, waitFor } from '@testing-library/react'
import { toast } from 'sonner'

import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useCreateClient } from '@/features/clients/hooks/useCreateClient'
import type { Client, CreateClientPayload } from '@/features/clients/types'

// ---------------------------------------------------------------------------
// Hoist mock before any imports resolve
// ---------------------------------------------------------------------------

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const validPayload: CreateClientPayload = {
  full_name: 'Ana Lima',
  phone: '+5511999999999',
  whatsapp_opt_in: false,
  email_opt_in: false,
}

function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: '1',
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

describe('useCreateClient', () => {
  it('chama POST /clients com o payload correto', async () => {
    let receivedBody: unknown = null

    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
      http.post(BASE_URL + '/clients', async ({ request }) => {
        receivedBody = await request.json()
        return HttpResponse.json(makeClient(), { status: 201 })
      }),
    )

    const { result } = renderHook(() => useCreateClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate(validPayload)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(receivedBody).toMatchObject(validPayload)
  })

  it('dispara toast.success após criação bem-sucedida', async () => {
    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
      http.post(BASE_URL + '/clients', () =>
        HttpResponse.json(makeClient(), { status: 201 }),
      ),
    )

    const { result } = renderHook(() => useCreateClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate(validPayload)
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(toast.success).toHaveBeenCalledWith('Cliente cadastrado com sucesso')
  })

  it('dispara toast.error em caso de falha na criação', async () => {
    server.use(
      http.post(BASE_URL + '/clients', () =>
        new HttpResponse(null, { status: 422 }),
      ),
    )

    const { result } = renderHook(() => useCreateClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate(validPayload)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(toast.error).toHaveBeenCalledWith('Erro ao cadastrar cliente')
  })
})
