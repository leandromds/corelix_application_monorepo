import { useState } from "react";
import { format, isSameDay, parseISO } from "date-fns";

import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/shared/Avatar";
import { StatusBadge } from "@/components/shared/StatusBadge";

import { useUpdateSession } from "../hooks/useUpdateSession";
import type { Session, SessionStatus } from "../types";
import { STATUS_LABELS } from "../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: string): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

const AVATAR_COLORS = [
  "#4f46e5",
  "#0891b2",
  "#059669",
  "#dc2626",
  "#7c3aed",
  "#d97706",
  "#0f766e",
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (const c of name) hash = (hash << 5) - hash + c.charCodeAt(0);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length] ?? "#4f46e5";
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DayListProps {
  sessions: Session[];
  date: Date;
  onSessionClick: (session: Session) => void;
  isLoading?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DayList({
  sessions,
  date,
  onSessionClick,
  isLoading,
}: DayListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { mutate: updateSession, isPending } = useUpdateSession();

  const sorted = [...sessions]
    .filter((s) => isSameDay(parseISO(s.scheduled_at), date))
    .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  // ------------------------------------------------------------------
  // Empty / loading states
  // ------------------------------------------------------------------

  if (isLoading) {
    return (
      <div
        className="p-12 text-center text-sm"
        style={{ color: "var(--text-muted)" }}
      >
        Carregando sessões…
      </div>
    );
  }

  if (sorted.length === 0) {
    return (
      <div className="p-12 text-center" style={{ color: "var(--text-muted)" }}>
        <p className="font-medium text-sm">Nenhuma sessão neste dia</p>
        <p className="text-xs mt-1">
          Clique em um horário na visualização semanal para agendar.
        </p>
      </div>
    );
  }

  // ------------------------------------------------------------------
  // Session list
  // ------------------------------------------------------------------

  return (
    <div>
      {sorted.map((session) => {
        const name = session.client_name ?? "Cliente";
        const isExpanded = expandedId === session.id;
        const rowBg = isExpanded ? "var(--bg-elevated)" : undefined;

        return (
          <div
            key={session.id}
            style={{ borderBottom: "1px solid var(--border-default)" }}
          >
            {/* Main row */}
            <div
              className="flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors"
              style={{ background: rowBg }}
              onClick={() => setExpandedId(isExpanded ? null : session.id)}
            >
              {/* Time */}
              <time
                className="w-12 shrink-0 text-sm font-mono font-medium tabular-nums"
                style={{ color: "var(--text-muted)" }}
                dateTime={session.scheduled_at}
              >
                {format(parseISO(session.scheduled_at), "HH:mm")}
              </time>

              {/* Avatar */}
              <Avatar
                initials={name
                  .split(" ")
                  .map((w: string) => w[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
                color={getAvatarColor(name)}
                size="sm"
              />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p
                  className="text-sm font-medium truncate"
                  style={{ color: "var(--text-primary)" }}
                >
                  {name}
                </p>
                <p
                  className="text-xs truncate"
                  style={{ color: "var(--text-muted)" }}
                >
                  Sessão · {session.duration_minutes} min ·{" "}
                  {formatCurrency(session.price)}
                </p>
              </div>

              {/* Status badge */}
              <StatusBadge status={session.status} />

              {/* Edit button — stops the row click / expand toggle */}
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 text-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  onSessionClick(session);
                }}
              >
                Editar
              </Button>
            </div>

            {/* Quick status change — shown when row is expanded */}
            {isExpanded && (
              <div
                className="flex flex-wrap gap-2 px-4 py-3"
                style={{
                  borderTop: "1px solid var(--border-default)",
                  background: "var(--bg-elevated)",
                }}
              >
                <span
                  className="text-xs font-medium self-center"
                  style={{ color: "var(--text-muted)" }}
                >
                  Alterar status:
                </span>

                {(Object.keys(STATUS_LABELS) as SessionStatus[]).map(
                  (status) => (
                    <Button
                      key={status}
                      variant={
                        session.status === status ? "default" : "outline"
                      }
                      size="sm"
                      className="text-xs h-7"
                      disabled={isPending}
                      onClick={() => {
                        updateSession(
                          { id: session.id, payload: { status } },
                          { onSuccess: () => setExpandedId(null) },
                        );
                      }}
                    >
                      {STATUS_LABELS[status]}
                    </Button>
                  ),
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
