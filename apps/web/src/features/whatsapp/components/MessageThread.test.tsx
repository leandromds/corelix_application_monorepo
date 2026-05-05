import { http, HttpResponse } from 'msw'

import { server, BASE_URL } from '@/test/server'
import { renderWithProviders, screen, waitFor } from '@/test/utils'
import { MessageThread } from './MessageThread'
import type { ConversationWithMessages } from '../types'

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

function makeDetail(
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
        content: 'Olá! Vou verificar os horários disponíveis.',
        sent_at: '2024-01-01T10:00:30Z',
      },
    ],
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MessageThread', () => {
  it('exibe estado vazio quando conversationId é null', () => {
    renderWithProviders(<MessageThread conversationId={null} />)

    expect(screen.getByText(/selecione uma conversa/i)).toBeInTheDocument()
  })

  it('renderiza mensagens após o fetch', async () => {
    server.use(
      http.get(BASE_URL + '/whatsapp/conversations/conv-1', () =>
        HttpResponse.json(makeDetail()),
      ),
    )

    renderWithProviders(<MessageThread conversationId="conv-1" />)

    expect(
      await screen.findByText('Olá, quero agendar uma consulta'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Olá! Vou verificar os horários disponíveis.'),
    ).toBeInTheDocument()
  })

  it('exibe botão "Assumir conversa" quando mode=ai e status=active', async () => {
    server.use(
      http.get(BASE_URL + '/whatsapp/conversations/conv-1', () =>
        HttpResponse.json(makeDetail()),
      ),
    )

    renderWithProviders(<MessageThread conversationId="conv-1" />)

    expect(
      await screen.findByRole('button', { name: /assumir conversa/i }),
    ).toBeInTheDocument()
  })

  it('não exibe botão handoff quando mode=handoff', async () => {
    const detail = makeDetail({
      conversation: {
        id: 'conv-1',
        client_phone: '+5511999999999',
        client_id: 'client-1',
        status: 'waiting_professional',
        mode: 'handoff',
        started_at: '2024-01-01T10:00:00Z',
        last_message_at: '2024-01-01T10:30:00Z',
        ended_at: null,
      },
    })

    server.use(
      http.get(BASE_URL + '/whatsapp/conversations/conv-1', () =>
        HttpResponse.json(detail),
      ),
    )

    renderWithProviders(<MessageThread conversationId="conv-1" />)

    await screen.findByText('Olá, quero agendar uma consulta')
    expect(
      screen.queryByRole('button', { name: /assumir conversa/i }),
    ).not.toBeInTheDocument()
  })

  it('envia POST ao clicar em "Assumir conversa" e exibe toast', async () => {
    const { toast } = await import('sonner')

    server.use(
      http.get(BASE_URL + '/whatsapp/conversations/conv-1', () =>
        HttpResponse.json(makeDetail()),
      ),
      http.post(BASE_URL + '/whatsapp/conversations/conv-1/handoff', () =>
        HttpResponse.json({ id: 'conv-1', mode: 'handoff', status: 'waiting_professional' }),
      ),
    )

    renderWithProviders(<MessageThread conversationId="conv-1" />)

    const btn = await screen.findByRole('button', { name: /assumir conversa/i })
    btn.click()

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith(
        expect.stringMatching(/assumida/i),
      ),
    )
  })
})
