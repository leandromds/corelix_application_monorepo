import { http, HttpResponse } from 'msw'
import { renderHook, act, waitFor } from '@testing-library/react'
import { toast } from 'sonner'

import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useDeleteClient } from '@/features/clients/hooks/useDeleteClient'

// ---------------------------------------------------------------------------
// Hoist mock before any imports resolve
// ---------------------------------------------------------------------------

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useDeleteClient', () => {
  it('chama DELETE /clients/:id com o id correto', async () => {
    let capturedId: string | undefined

    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
      http.delete(BASE_URL + '/clients/:id', ({ params }) => {
        capturedId = params['id'] as string
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const { result } = renderHook(() => useDeleteClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate('client-42')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(capturedId).toBe('client-42')
  })

  it('dispara toast.success após desativação bem-sucedida', async () => {
    server.use(
      http.get(BASE_URL + '/clients', () => HttpResponse.json([])),
      http.delete(BASE_URL + '/clients/:id', () =>
        new HttpResponse(null, { status: 204 }),
      ),
    )

    const { result } = renderHook(() => useDeleteClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate('client-42')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(toast.success).toHaveBeenCalledWith('Cliente desativado')
  })

  it('dispara toast.error em caso de falha na desativação', async () => {
    server.use(
      http.delete(BASE_URL + '/clients/:id', () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    const { result } = renderHook(() => useDeleteClient(), { wrapper: makeWrapper() })

    act(() => {
      result.current.mutate('client-42')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(toast.error).toHaveBeenCalledWith('Erro ao desativar cliente')
  })
})
