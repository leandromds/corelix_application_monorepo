import { Users } from "lucide-react";

import { useDeleteClient } from "../hooks/useDeleteClient";
import { useUpdateClient } from "../hooks/useUpdateClient";
import type { Client } from "../types";

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
} from "@/components/ui/alert-dialog";

// ---------------------------------------------------------------------------
// Avatar color palette — index-based (cycles through 5 colors)
// ---------------------------------------------------------------------------

const AVATAR_PALETTE = [
  {
    bg: "rgba(99,102,241,0.25)",
    border: "rgba(99,102,241,0.5)",
    text: "#a5b4fc",
  },
  {
    bg: "rgba(6,182,212,0.20)",
    border: "rgba(6,182,212,0.4)",
    text: "#67e8f9",
  },
  {
    bg: "rgba(52,211,153,0.20)",
    border: "rgba(52,211,153,0.4)",
    text: "#6ee7b7",
  },
  {
    bg: "rgba(248,113,113,0.20)",
    border: "rgba(248,113,113,0.4)",
    text: "#fca5a5",
  },
  {
    bg: "rgba(251,191,36,0.20)",
    border: "rgba(251,191,36,0.4)",
    text: "#fcd34d",
  },
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = words[0]![0]!.toUpperCase();
  if (words.length === 1) return first;
  return `${first}${words[1]![0]!.toUpperCase()}`;
}

// ---------------------------------------------------------------------------
// Column headers (8 columns — actions has no header text)
// ---------------------------------------------------------------------------

const COLUMN_HEADERS = [
  "Nome",
  "Telefone",
  "Tipo",
  "Sessões",
  "Valor/sessão",
  "Última sessão",
  "Status",
  "Ações",
] as const;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ClientListProps {
  clients: Client[];
  isLoading: boolean;
  onEdit: (client: Client) => void;
  /** Called when the empty-state CTA is clicked. */
  onNewClient?: () => void;
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function SkeletonRows() {
  const barStyle: React.CSSProperties = {
    borderRadius: 4,
    backgroundColor: "var(--border-default)",
  };

  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <tr key={i}>
          {/* Nome */}
          <td style={{ padding: "11px 14px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                className="animate-pulse"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  backgroundColor: "var(--border-default)",
                  flexShrink: 0,
                }}
              />
              <div
                className="animate-pulse"
                style={{ ...barStyle, width: 110, height: 13 }}
              />
            </div>
          </td>
          {/* Telefone */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 96, height: 13 }}
            />
          </td>
          {/* Tipo */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 72, height: 13 }}
            />
          </td>
          {/* Sessões */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 32, height: 13 }}
            />
          </td>
          {/* Valor/sessão */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 56, height: 13 }}
            />
          </td>
          {/* Última sessão */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 80, height: 13 }}
            />
          </td>
          {/* Status */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 60, height: 20, borderRadius: 20 }}
            />
          </td>
          {/* Actions */}
          <td style={{ padding: "11px 14px" }}>
            <div
              className="animate-pulse"
              style={{ ...barStyle, width: 40, height: 24 }}
            />
          </td>
        </tr>
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

interface EmptyStateProps {
  onNewClient?: () => void;
}

function EmptyState({ onNewClient }: EmptyStateProps) {
  return (
    <tr>
      <td colSpan={8}>
        <div className="empty-state">
          <div className="empty-icon">
            <Users aria-hidden="true" style={{ width: 32, height: 32 }} />
          </div>
          <p className="empty-title">Adicione seu primeiro cliente</p>
          <p className="empty-desc">
            Cadastre clientes para organizar sua agenda.
          </p>
          {onNewClient && (
            <button
              type="button"
              className="btn-primary"
              onClick={onNewClient}
              style={{
                marginTop: 12,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              + Novo cliente
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ClientList({
  clients,
  isLoading,
  onEdit,
  onNewClient,
}: ClientListProps) {
  const { mutate: deleteClient, isPending: isDeleting } = useDeleteClient();
  const { mutate: updateClient, isPending: isUpdating } = useUpdateClient();

  // Disable all action buttons while any mutation is in-flight
  const isActing = isDeleting || isUpdating;

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table">
        <thead>
          <tr>
            {COLUMN_HEADERS.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>

        <tbody>
          {isLoading ? (
            <SkeletonRows />
          ) : clients.length === 0 ? (
            <EmptyState onNewClient={onNewClient} />
          ) : (
            clients.map((client, idx) => {
              const palette = AVATAR_PALETTE[idx % AVATAR_PALETTE.length]!;

              return (
                <tr key={client.id}>
                  {/* Nome */}
                  <td>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                      }}
                    >
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "50%",
                          background: palette.bg,
                          border: `1px solid ${palette.border}`,
                          color: palette.text,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 10,
                          fontWeight: 700,
                          flexShrink: 0,
                          letterSpacing: "0.03em",
                        }}
                        aria-label={client.full_name}
                      >
                        {getInitials(client.full_name)}
                      </div>
                      <span
                        style={{
                          fontWeight: 600,
                          color: "var(--text-primary)",
                          fontSize: 13,
                        }}
                      >
                        {client.full_name}
                      </span>
                    </div>
                  </td>

                  {/* Telefone */}
                  <td style={{ color: "var(--text-muted)", fontSize: 13 }}>
                    {client.phone ?? "—"}
                  </td>

                  {/* Tipo — not yet in Client type */}
                  <td style={{ color: "var(--text-muted)", fontSize: 13 }}>
                    —
                  </td>

                  {/* Sessões — not yet in Client type */}
                  <td
                    style={{
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      fontSize: 13,
                    }}
                  >
                    —
                  </td>

                  {/* Valor/sessão — not yet in Client type */}
                  <td style={{ color: "var(--text-muted)", fontSize: 13 }}>
                    —
                  </td>

                  {/* Última sessão — not yet in Client type */}
                  <td style={{ color: "var(--text-muted)", fontSize: 13 }}>
                    —
                  </td>

                  {/* Status */}
                  <td>
                    <span
                      className={
                        client.is_active ? "badge-confirmed" : "badge-noshow"
                      }
                    >
                      {client.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </td>

                  {/* Actions */}
                  <td>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      {/* Ver / Editar */}
                      <button
                        type="button"
                        className="btn-secondary"
                        disabled={isActing}
                        onClick={() => onEdit(client)}
                        style={{ fontSize: 10, padding: "3px 10px" }}
                      >
                        Ver
                      </button>

                      {/* Desativar (active) / Reativar (inactive) */}
                      {client.is_active ? (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <button
                              type="button"
                              className="btn-secondary"
                              disabled={isActing}
                              style={{ fontSize: 10, padding: "3px 10px" }}
                            >
                              Desativar
                            </button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                Desativar {client.full_name}?
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                Esta ação desativa o cliente. Você pode
                                reativá-lo a qualquer momento.
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
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={isActing}
                          onClick={() =>
                            updateClient({
                              id: client.id,
                              payload: { is_active: true },
                            })
                          }
                          style={{ fontSize: 10, padding: "3px 10px" }}
                        >
                          Reativar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
