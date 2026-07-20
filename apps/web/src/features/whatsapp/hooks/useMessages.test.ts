import { http, HttpResponse } from 'msw'
import { renderHook, waitFor } from '@testing-library/react'

import { server, BASE_URL } from '@/test/server'
import { makeWrapper } from '@/test/utils'
import { useMessages } from './useMessages'
import type { ConversationWithMessages } from '../types'

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeConversationWithMessages(
  overrides: Partial<ConversationWithMessages> = {},
): ConversationWithMessages {
  return {
    conversation: {
      id: 'conv-1',
      client_phone: '+5511999999999',
      client_id: 'client-1',
      status: 'active',
      mode: 'ai',
      started_at: '2024-01-01T10:00:00Z',
      last_message_at: '2024-01-01T10:30:00Z',
      ended_at: null,
    },
    messages: [
      {
        id: 'msg-1',
        direction: 'inbound',
        sender_type: 'client',
        content: 'Olá, quero agendar uma consulta',
        sent_at: '2024-01-01T10:00:00Z',
      },
      {
        id: 'msg-2',
        direction: 'outbound',
        sender_type: 'ai',
        content: 'Olá! Claro, vou verificar os horários disponíveis.',
        sent_at: '2024-01-01T10:00:30Z',
      },
    ],
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useMessages', () => {
  it('retorna conversa com mensagens quando conversationId é fornecido', async () => {
    const detail = makeConversationWithMessages()

    server.use(
      http.get(BASE_URL + '/whatsapp/conversations/conv-1', () =>
        HttpResponse.json(detail),
      ),
    )

    const { result } = renderHook(() => useMessages('conv-1'), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.messages).toHaveLength(2)
    expect(result.current.data?.conversation.id).toBe('conv-1')
  })

  it('não faz fetch quando conversationId é null (query desabilitada)', () => {
    const { result } = renderHook(() => useMessages(null), {
      wrapper: makeWrapper(),
    })

    // enabled: false → fetchStatus fica 'idle', dados undefined
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })

  it('expõe isError em caso de 404', async () => {
    server.use(
      http.get(BASE_URL + '/whatsapp/conversations/missing', () =>
        new HttpResponse(null, { status: 404 }),
      ),
    )

    const { result } = renderHook(() => useMessages('missing'), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
