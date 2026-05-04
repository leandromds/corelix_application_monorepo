import { http, HttpResponse } from 'msw'
import { renderHook, waitFor } from '@testing-library/react'

import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useClients } from '@/features/clients/hooks/useClients'
import type { Client } from '@/features/clients/types'

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

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

describe('useClients', () => {
  it('retorna lista de clientes em caso de sucesso', async () => {
    const clients = [makeClient({ id: '1' }), makeClient({ id: '2', full_name: 'João Silva' })]

    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json(clients)),
    )

    const { result } = renderHook(() => useClients(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toEqual(clients)
    expect(result.current.data).toHaveLength(2)
  })

  it('passa parâmetro is_active na query string quando fornecido', async () => {
    const capturedUrls: string[] = []

    server.use(
      http.get(BASE_URL + '/clients', ({ request }) => {
        capturedUrls.push(request.url)
        return HttpResponse.json([makeClient()])
      }),
    )

    const { result } = renderHook(
      () => useClients({ is_active: false }),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedUrls[0]).toContain('is_active=false')
  })

  it('expõe isError em caso de falha HTTP (5xx)', async () => {
    // Usa 500 para não disparar o interceptor de refresh de 401
    server.use(
      http.get(BASE_URL + '/clients', () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    const { result } = renderHook(() => useClients(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.data).toBeUndefined()
  })
})
