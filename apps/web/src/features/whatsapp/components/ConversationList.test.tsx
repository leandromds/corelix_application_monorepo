import userEvent from '@testing-library/user-event'

import { renderWithProviders, screen } from '@/test/utils'
import { ConversationList } from './ConversationList'
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

describe('ConversationList', () => {
  it('exibe skeleton de carregamento quando isLoading=true', () => {
    renderWithProviders(
      <ConversationList
        conversations={[]}
        isLoading={true}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    )

    const pulsingEls = document.querySelectorAll('.animate-pulse')
    expect(pulsingEls.length).toBeGreaterThan(0)
  })

  it('renderiza itens de conversa após carregar', () => {
    const conversations = [
      makeConversation({ id: 'conv-1', client_phone: '+5511999999991' }),
      makeConversation({ id: 'conv-2', client_phone: '+5511999999992', status: 'resolved' }),
    ]

    renderWithProviders(
      <ConversationList
        conversations={conversations}
        isLoading={false}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('+5511999999991')).toBeInTheDocument()
    expect(screen.getByText('+5511999999992')).toBeInTheDocument()
  })

  it('exibe estado vazio quando a lista está vazia', () => {
    renderWithProviders(
      <ConversationList
        conversations={[]}
        isLoading={false}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByText(/nenhuma conversa/i)).toBeInTheDocument()
  })

  it('destaca a conversa selecionada via aria-current', () => {
    const conversations = [makeConversation({ id: 'conv-1' })]

    renderWithProviders(
      <ConversationList
        conversations={conversations}
        isLoading={false}
        selectedId="conv-1"
        onSelect={vi.fn()}
      />,
    )

    const item = screen.getByRole('button', { name: /\+5511999999999/i })
    expect(item).toHaveAttribute('aria-current', 'true')
  })

  it('chama onSelect com o id correto ao clicar em uma conversa', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const conversations = [makeConversation({ id: 'conv-42' })]

    renderWithProviders(
      <ConversationList
        conversations={conversations}
        isLoading={false}
        selectedId={null}
        onSelect={onSelect}
      />,
    )

    await user.click(screen.getByRole('button', { name: /\+5511999999999/i }))
    expect(onSelect).toHaveBeenCalledWith('conv-42')
  })
})
