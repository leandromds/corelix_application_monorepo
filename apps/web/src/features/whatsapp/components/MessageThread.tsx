/**
 * MessageThread — shows the message history for a selected conversation.
 *
 * Internally calls useMessages(conversationId) so the parent (WhatsAppPage)
 * only needs to pass the selected ID — no prop-drilling of message data.
 *
 * Layout:
 *  - inbound  (client)                  → bubble aligned LEFT
 *  - outbound (ai | professional)       → bubble aligned RIGHT
 *
 * Handoff button appears only when:
 *   conversation.mode === 'ai' && conversation.status === 'active'
 */

import { useMessages } from '../hooks/useMessages'
import { useHandoff } from '../hooks/useHandoff'
import { Button } from '@/components/ui/button'
import type { Message, ConversationMode, ConversationStatus } from '../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return ''
  }
}

// ---------------------------------------------------------------------------
// Bubble
// ---------------------------------------------------------------------------

interface BubbleProps {
  message: Message
}

function Bubble({ message }: BubbleProps) {
  const isOutbound = message.direction === 'outbound'
  const senderLabel =
    message.sender_type === 'ai'
      ? 'Secretária IA'
      : message.sender_type === 'professional'
        ? 'Profissional'
        : 'Cliente'

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isOutbound ? 'flex-end' : 'flex-start',
        marginBottom: 12,
      }}
    >
      {/* Sender label */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          color: 'var(--text-muted)',
          marginBottom: 2,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        {senderLabel}
      </span>

      {/* Bubble */}
      <div
        style={{
          maxWidth: '72%',
          padding: '8px 12px',
          borderRadius: isOutbound ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          background: isOutbound
            ? 'var(--color-primary, #2563eb)'
            : 'var(--bg-surface-card, #f1f5f9)',
          color: isOutbound ? '#fff' : 'var(--text-primary)',
          fontSize: 13,
          lineHeight: 1.5,
          wordBreak: 'break-word',
        }}
      >
        {message.content}
      </div>

      {/* Timestamp */}
      <span style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
        {formatTime(message.sent_at)}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface MessageThreadProps {
  conversationId: string | null
}

// ---------------------------------------------------------------------------
// MessageThread
// ---------------------------------------------------------------------------

export function MessageThread({ conversationId }: MessageThreadProps) {
  const { data, isLoading } = useMessages(conversationId)
  const handoff = useHandoff()

  // ── Empty state ──────────────────────────────────────────────────────────
  if (!conversationId) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: 14,
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 32 }}>💬</span>
        <span>Selecione uma conversa para ver o histórico.</span>
      </div>
    )
  }

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div style={{ flex: 1, padding: 24 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="animate-pulse"
            style={{
              marginBottom: 16,
              display: 'flex',
              flexDirection: 'column',
              alignItems: i % 2 === 0 ? 'flex-start' : 'flex-end',
            }}
          >
            <div
              style={{
                height: 36,
                width: `${40 + (i % 3) * 15}%`,
                borderRadius: 12,
                background: 'rgba(0,0,0,0.07)',
              }}
            />
          </div>
        ))}
      </div>
    )
  }

  const conversation = data?.conversation
  const messages = data?.messages ?? []

  const canHandoff =
    (conversation?.mode as ConversationMode) === 'ai' &&
    (conversation?.status as ConversationStatus) === 'active'

  // ── Thread ───────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--border-default)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
          {conversation?.client_phone ?? '—'}
        </span>

        {canHandoff && (
          <Button
            size="sm"
            onClick={() => handoff.mutate(conversationId)}
            disabled={handoff.isPending}
            aria-label="Assumir conversa"
          >
            {handoff.isPending ? 'Assumindo…' : 'Assumir conversa'}
          </Button>
        )}
      </div>

      {/* Messages scrollable area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px 20px',
        }}
      >
        {messages.length === 0 ? (
          <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            Nenhuma mensagem nesta conversa.
          </p>
        ) : (
          messages.map((msg) => <Bubble key={msg.id} message={msg} />)
        )}
      </div>
    </div>
  )
}
