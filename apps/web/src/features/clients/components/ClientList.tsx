import { useDeleteClient } from '../hooks/useDeleteClient'
import { useUpdateClient } from '../hooks/useUpdateClient'
import type { Client } from '../types'

import { Avatar, getInitials } from '@/components/shared/Avatar'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

// ---------------------------------------------------------------------------
// Avatar color — deterministic hash from name
// ---------------------------------------------------------------------------

const AVATAR_COLORS = [
  '#4f46e5',
  '#0891b2',
  '#059669',
  '#dc2626',
  '#7c3aed',
  '#d97706',
  '#0f766e',
]

function getAvatarColor(name: string): string {
  let hash = 0
  for (const c of name) hash = (hash << 5) - hash + c.charCodeAt(0)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]!
}

// ---------------------------------------------------------------------------
// Table header labels (shared between loading skeleton and live table)
// ---------------------------------------------------------------------------

const COLUMN_HEADERS = ['Nome', 'Telefone', 'E-mail', 'Status', ''] as const

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '12px 16px',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text-muted)',
  borderBottom: '1px solid var(--border-default)',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '12px 16px',
  fontSize: 14,
  verticalAlign: 'middle',
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ClientListProps {
  clients: Client[]
  isLoading: boolean
  onEdit: (client: Client) => void
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <tr key={i} style={{ borderBottom: '1px solid var(--border-default)' }}>
          {/* Nome */}
          <td style={tdStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div
                className="animate-pulse rounded-full"
                style={{ width: 32, height: 32, backgroundColor: 'var(--border-default)', flexShrink: 0 }}
              />
              <div
                className="animate-pulse rounded"
                style={{ width: 120, height: 14, backgroundColor: 'var(--border-default)' }}
              />
            </div>
          </td>
          {/* Telefone */}
          <td style={tdStyle}>
            <div
              className="animate-pulse rounded"
              style={{ width: 100, height: 14, backgroundColor: 'var(--border-default)' }}
            />
          </td>
          {/* E-mail */}
          <td style={tdStyle}>
            <div
              className="animate-pulse rounded"
              style={{ width: 140, height: 14, backgroundColor: 'var(--border-default)' }}
            />
          </td>
          {/* Status */}
          <td style={tdStyle}>
            <div
              className="animate-pulse rounded-full"
              style={{ width: 64, height: 22, backgroundColor: 'var(--border-default)' }}
            />
          </td>
          {/* Actions */}
          <td style={tdStyle}>
            <div
              className="animate-pulse rounded"
              style={{ width: 80, height: 28, backgroundColor: 'var(--border-default)' }}
            />
          </td>
        </tr>
      ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <tr>
      <td colSpan={5}>
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div style={{ fontSize: 40 }}>👥</div>
          <p
            style={{
              fontFamily: 'var(--font-heading)',
              fontWeight: 700,
              color: 'var(--text-primary)',
            }}
          >
            Nenhum cliente encontrado
          </p>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Tente ajustar os filtros ou adicione um novo cliente.
          </p>
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ClientList({ clients, isLoading, onEdit }: ClientListProps) {
  const { mutate: deleteClient, isPending: isDeleting } = useDeleteClient()
  const { mutate: updateClient, isPending: isUpdating } = useUpdateClient()

  // Disable all action buttons while any mutation is in-flight
  const isActing = isDeleting || isUpdating

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {COLUMN_HEADERS.map((h) => (
              <th key={h} style={thStyle}>
                {h}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {isLoading ? (
            <SkeletonRows />
          ) : clients.length === 0 ? (
            <EmptyState />
          ) : (
            clients.map((client) => (
              <tr
                key={client.id}
                style={{ borderBottom: '1px solid var(--border-default)', transition: 'background 0.15s ease' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--bg-surface)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = ''
                }}
              >
                {/* Nome */}
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Avatar
                      initials={getInitials(client.full_name)}
                      color={getAvatarColor(client.full_name)}
                      size="sm"
                    />
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {client.full_name}
                    </span>
                  </div>
                </td>

                {/* Telefone */}
                <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>
                  {client.phone}
                </td>

                {/* E-mail */}
                <td
                  style={{
                    ...tdStyle,
                    color: client.email ? 'var(--text-primary)' : 'var(--text-muted)',
                  }}
                >
                  {client.email ?? '—'}
                </td>

                {/* Status */}
                <td style={tdStyle}>
                  <StatusBadge status={client.is_active ? 'active' : 'inactive'} />
                </td>

                {/* Actions */}
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {/* Edit */}
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={isActing}
                      onClick={() => onEdit(client)}
                    >
                      Editar
                    </Button>

                    {/* Desativar (active) / Reativar (inactive) */}
                    {client.is_active ? (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="sm" variant="secondary" disabled={isActing}>
                            Desativar
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>
                              Desativar {client.full_name}?
                            </AlertDialogTitle>
                            <AlertDialogDescription>
                              Esta ação desativa o cliente. Você pode reativá-lo a qualquer momento.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancelar</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => deleteClient(client.id)}
                            >
                              Desativar
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    ) : (
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={isActing}
                        onClick={() =>
                          updateClient({ id: client.id, payload: { is_active: true } })
                        }
                      >
                        Reativar
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
