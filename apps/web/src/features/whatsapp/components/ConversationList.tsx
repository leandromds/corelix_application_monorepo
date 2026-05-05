/**
 * ConversationList — stateless list of WhatsApp conversations.
 *
 * Props:
 * - conversations: already-fetched list (parent owns the query)
 * - isLoading: shows skeleton rows while data arrives
 * - selectedId: highlights the currently open conversation
 * - onSelect: called with conversation.id when user clicks an item
 *
 * Status colours:
 *   active              → green
 *   resolved            → gray
 *   waiting_professional → amber
 *
 * Mode colours:
 *   ai      → purple
 *   handoff → blue
 */

import { cn } from '@/lib/utils'
import type { Conversation, ConversationStatus, ConversationMode } from '../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_LABEL: Record<ConversationStatus, string> = {
  active: 'Ativa',
  resolved: 'Resolvida',
  waiting_professional: 'Aguardando',
}

const MODE_LABEL: Record<ConversationMode, string> = {
  ai: 'IA',
  handoff: 'Profissional',
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className="animate-pulse flex flex-col gap-2 p-4 border-b border-[var(--border-default)]">
      <div className="h-3 w-32 rounded bg-[rgba(0,0,0,0.08)]" />
      <div className="h-2 w-48 rounded bg-[rgba(0,0,0,0.05)]" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status / Mode badges (inline — no external dep needed)
// ---------------------------------------------------------------------------

interface InlineBadgeProps {
  label: string
  variant: 'green' | 'gray' | 'amber' | 'purple' | 'blue'
}

const BADGE_STYLES: Record<InlineBadgeProps['variant'], React.CSSProperties> = {
  green: { background: 'rgba(34,197,94,0.12)', color: '#16a34a', border: '1px solid rgba(34,197,94,0.3)' },
  gray: { background: 'rgba(100,116,139,0.12)', color: '#64748b', border: '1px solid rgba(100,116,139,0.3)' },
  amber: { background: 'rgba(251,191,36,0.12)', color: '#d97706', border: '1px solid rgba(251,191,36,0.3)' },
  purple: { background: 'rgba(168,85,247,0.12)', color: '#9333ea', border: '1px solid rgba(168,85,247,0.3)' },
  blue: { background: 'rgba(59,130,246,0.12)', color: '#2563eb', border: '1px solid rgba(59,130,246,0.3)' },
}

function InlineBadge({ label, variant }: InlineBadgeProps) {
  return (
    <span
      style={{
        ...BADGE_STYLES[variant],
        fontSize: '10px',
        fontWeight: 600,
        padding: '1px 6px',
        borderRadius: 4,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  )
}

function statusVariant(status: ConversationStatus): InlineBadgeProps['variant'] {
  if (status === 'active') return 'green'
  if (status === 'waiting_professional') return 'amber'
  return 'gray'
}

function modeVariant(mode: ConversationMode): InlineBadgeProps['variant'] {
  return mode === 'ai' ? 'purple' : 'blue'
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ConversationListProps {
  conversations: Conversation[]
  isLoading: boolean
  selectedId: string | null
  onSelect: (id: string) => void
}

// ---------------------------------------------------------------------------
// ConversationList
// ---------------------------------------------------------------------------

export function ConversationList({
  conversations,
  isLoading,
  selectedId,
  onSelect,
}: ConversationListProps) {
  if (isLoading) {
    return (
      <div>
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    )
  }

  if (conversations.length === 0) {
    return (
      <div
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: 14,
        }}
      >
        Nenhuma conversa encontrada.
      </div>
    )
  }

  return (
    <div role="list">
      {conversations.map((conv) => {
        const isSelected = conv.id === selectedId

        return (
          <button
            key={conv.id}
            role="button"
            aria-label={conv.client_phone}
            aria-current={isSelected ? 'true' : undefined}
            onClick={() => onSelect(conv.id)}
            className={cn(
              'w-full text-left px-4 py-3 flex flex-col gap-1',
              'border-b border-[var(--border-default)]',
              'transition-colors duration-150 cursor-pointer',
              isSelected
                ? 'bg-[rgba(0,0,0,0.06)] font-semibold'
                : 'hover:bg-[rgba(0,0,0,0.03)]',
            )}
            style={{
              borderLeft: isSelected
                ? '3px solid var(--color-primary)'
                : '3px solid transparent',
              background: 'none',
              outline: 'none',
            }}
          >
            {/* Phone number */}
            <span
              style={{
                fontSize: 13,
                fontWeight: isSelected ? 600 : 500,
                color: 'var(--text-primary)',
              }}
            >
              {conv.client_phone}
            </span>

            {/* Badges + time row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <InlineBadge
                label={STATUS_LABEL[conv.status]}
                variant={statusVariant(conv.status)}
              />
              <InlineBadge
                label={MODE_LABEL[conv.mode]}
                variant={modeVariant(conv.mode)}
              />
              <span
                style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}
              >
                {formatDate(conv.last_message_at)}
              </span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
