/**
 * BillingTable — per-client billing report with expandable session rows.
 *
 * Each client row shows: client name | session count | total amount.
 * Clicking the chevron expands the row to reveal the individual sessions.
 * Collapse state is local to each row — no lifting needed.
 *
 * Accessibility:
 *   - Expand/collapse button has aria-label + aria-expanded
 *   - aria-label flips between "Expandir" and "Colapsar" on toggle
 *   - Table has visible column headers (scope="col")
 */

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { ptBR } from 'date-fns/locale'

import { StatusBadge } from '@/components/shared/StatusBadge'
import type { ClientBillingEntry, SessionEntry, SessionStatus } from '../types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(amount: string): string {
  return new Intl.NumberFormat('pt-BR', {
    style:    'currency',
    currency: 'BRL',
  }).format(Number(amount))
}

function formatDateTime(iso: string): string {
  return format(parseISO(iso), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })
}

// ---------------------------------------------------------------------------
// ClientRow — summary row + inline expanded sessions
// ---------------------------------------------------------------------------

interface ClientRowProps {
  entry: ClientBillingEntry
}

function ClientRow({ entry }: ClientRowProps) {
  const [expanded, setExpanded] = useState(false)

  const expandLabel = expanded
    ? `Colapsar sessões de ${entry.client_name}`
    : `Expandir sessões de ${entry.client_name}`

  return (
    <>
      {/* ── Summary row ── */}
      <tr>
        <td
          style={{
            padding:      '12px 16px',
            borderBottom: '1px solid var(--border-default)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Expand / collapse toggle */}
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              aria-label={expandLabel}
              aria-expanded={expanded}
              style={{
                background:  'none',
                border:      'none',
                cursor:      'pointer',
                padding:     4,
                display:     'flex',
                alignItems:  'center',
                color:       'var(--text-muted)',
                borderRadius: 4,
                flexShrink:  0,
              }}
            >
              {expanded
                ? <ChevronDown  aria-hidden="true" size={16} />
                : <ChevronRight aria-hidden="true" size={16} />
              }
            </button>

            <span
              style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}
            >
              {entry.client_name}
            </span>
          </div>
        </td>

        <td
          style={{
            padding:      '12px 16px',
            borderBottom: '1px solid var(--border-default)',
            textAlign:    'center',
          }}
        >
          <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>
            {entry.session_count}{' '}
            {entry.session_count === 1 ? 'sessão' : 'sessões'}
          </span>
        </td>

        <td
          style={{
            padding:      '12px 16px',
            borderBottom: '1px solid var(--border-default)',
            textAlign:    'right',
          }}
        >
          <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 15 }}>
            {formatCurrency(entry.total_amount)}
          </span>
        </td>
      </tr>

      {/* ── Expanded session rows ── */}
      {expanded &&
        entry.sessions.map((session: SessionEntry) => (
          <tr
            key={session.session_id}
            style={{ background: 'var(--bg-surface)' }}
          >
            <td
              colSpan={3}
              style={{
                padding:      '0 16px',
                borderBottom: '1px solid var(--border-default)',
              }}
            >
              <div
                style={{
                  display:     'flex',
                  alignItems:  'center',
                  gap:         16,
                  padding:     '10px 8px 10px 36px',
                  flexWrap:    'wrap',
                }}
              >
                <span
                  style={{
                    fontSize: 13,
                    color:    'var(--text-primary)',
                    flex:     1,
                    minWidth: 160,
                  }}
                >
                  {formatDateTime(session.scheduled_at)}
                </span>

                <span style={{ fontSize: 13, color: 'var(--text-muted)', minWidth: 80 }}>
                  {session.duration_minutes} min
                </span>

                <span
                  style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', minWidth: 90 }}
                >
                  {formatCurrency(session.price)}
                </span>

                <StatusBadge status={session.status as SessionStatus} />

                {session.notes && (
                  <span
                    style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}
                  >
                    {session.notes}
                  </span>
                )}
              </div>
            </td>
          </tr>
        ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// BillingTable
// ---------------------------------------------------------------------------

interface BillingTableProps {
  clients: ClientBillingEntry[]
}

export function BillingTable({ clients }: BillingTableProps) {
  // Empty state — rendered inside the card shell so it keeps the border/shadow
  if (clients.length === 0) {
    return (
      <div
        style={{
          padding:    '48px 24px',
          textAlign:  'center',
          color:      'var(--text-muted)',
          fontSize:   14,
        }}
      >
        <div style={{ fontSize: 32, marginBottom: 12 }} aria-hidden="true">📭</div>
        <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-primary)' }}>
          Nenhuma sessão encontrada
        </p>
        <p style={{ margin: '4px 0 0', fontSize: 12 }}>
          Tente ajustar os filtros de período ou status.
        </p>
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: 'var(--bg-surface)' }}>
            <th
              scope="col"
              style={{
                padding:       '10px 16px',
                textAlign:     'left',
                fontSize:      11,
                fontWeight:    700,
                color:         'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              Cliente
            </th>
            <th
              scope="col"
              style={{
                padding:       '10px 16px',
                textAlign:     'center',
                fontSize:      11,
                fontWeight:    700,
                color:         'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              Sessões
            </th>
            <th
              scope="col"
              style={{
                padding:       '10px 16px',
                textAlign:     'right',
                fontSize:      11,
                fontWeight:    700,
                color:         'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {clients.map((entry) => (
            <ClientRow key={entry.client_id} entry={entry} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
