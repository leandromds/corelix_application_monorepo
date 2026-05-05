import { http, HttpResponse } from 'msw'
import { renderHook, waitFor } from '@testing-library/react'

import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useConversations } from './useConversations'
import type { Conversation } from '../types'

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'conv-1',
    client_phone: '+5511999999999',
    client_id: 'client-1',
    status: 'active',
    mode: 'ai',
    started_at: '2024-01-01T10:00:00Z',
    last_message_at: '2024-01-01T10:30:00Z',
    ended_at: null,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useConversations', () => {
  it('retorna lista de conversas em caso de sucesso', async () => {
    const conversations = [
      makeConversation({ id: 'conv-1' }),
      makeConversation({ id: 'conv-2', status: 'resolved' }),
    ]

    server.use(
      http.get(BASE_URL + '/whatsapp/conversations', () =>
        HttpResponse.json(conversations),
      ),
    )

    const { result } = renderHook(() => useConversations(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(2)
    expect(result.current.data![0].id).toBe('conv-1')
  })

  it('passa status como query param quando fornecido', async () => {
    const capturedUrls: string[] = []

    server.use(
      http.get(BASE_URL + '/whatsapp/conversations', ({ request }) => {
        capturedUrls.push(request.url)
        return HttpResponse.json([makeConversation()])
      }),
    )

    const { result } = renderHook(() => useConversations('active'), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(capturedUrls[0]).toContain('status=active')
  })

  it('não inclui o param status quando não fornecido', async () => {
    const capturedUrls: string[] = []

    server.use(
      http.get(BASE_URL + '/whatsapp/conversations', ({ request }) => {
        capturedUrls.push(request.url)
        return HttpResponse.json([])
      }),
    )

    const { result } = renderHook(() => useConversations(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(capturedUrls[0]).not.toContain('status=')
  })

  it('expõe isError em caso de falha HTTP (5xx)', async () => {
    server.use(
      http.get(BASE_URL + '/whatsapp/conversations', () =>
        new HttpResponse(null, { status: 500 }),
      ),
    )

    const { result } = renderHook(() => useConversations(), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})
