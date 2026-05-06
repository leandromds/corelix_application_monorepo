import { useState } from "react";
import {
  format,
  addWeeks,
  subWeeks,
  addDays,
  subDays,
  isSameDay,
  parseISO,
} from "date-fns";
import { ptBR } from "date-fns/locale";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";

import { useSessions } from "./hooks/useSessions";
import { WeekView } from "./components/WeekView";
import { DayList } from "./components/DayList";
import { SessionForm } from "./components/SessionForm";
import type { Session, SessionStatus } from "./types";
import { STATUS_LABELS } from "./types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "week" | "day";

// ---------------------------------------------------------------------------
// Avatar color variants — cycled by name hash
// ---------------------------------------------------------------------------

const AVATAR_VARIANTS = [
  {
    bg: "rgba(99,102,241,0.25)",
    border: "rgba(99,102,241,0.5)",
    color: "#a5b4fc",
  },
  {
    bg: "rgba(34,211,238,0.20)",
    border: "rgba(34,211,238,0.5)",
    color: "#67e8f9",
  },
  {
    bg: "rgba(52,211,153,0.20)",
    border: "rgba(52,211,153,0.5)",
    color: "#6ee7b7",
  },
  {
    bg: "rgba(251,191,36,0.20)",
    border: "rgba(251,191,36,0.5)",
    color: "#fcd34d",
  },
  {
    bg: "rgba(248,113,113,0.20)",
    border: "rgba(248,113,113,0.5)",
    color: "#fca5a5",
  },
] as const;

function getAvatarVariant(name: string) {
  let h = 0;
  for (const c of name) h = (h << 5) - h + c.charCodeAt(0);
  return AVATAR_VARIANTS[Math.abs(h) % AVATAR_VARIANTS.length]!;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateTime(iso: string): string {
  return format(parseISO(iso), "dd/MM 'às' HH:mm", { locale: ptBR });
}

// Status → badge CSS class
const STATUS_BADGE: Record<SessionStatus, string> = {
  scheduled: "badge-confirmed",
  completed: "badge-confirmed",
  cancelled: "badge-cancelled",
  no_show: "badge-noshow",
};

// ---------------------------------------------------------------------------
// UpcomingSessionsTable
// ---------------------------------------------------------------------------

interface UpcomingTableProps {
  sessions: Session[];
  onEditSession: (session: Session) => void;
}

function UpcomingSessionsTable({
  sessions,
  onEditSession,
}: UpcomingTableProps) {
  const now = new Date();
  const upcoming = sessions
    .filter((s) => s.status === "scheduled" && new Date(s.scheduled_at) > now)
    .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))
    .slice(0, 20);

  if (upcoming.length === 0) return null;

  return (
    <div className="glass-card animate-slide-up animate-delay-2">
      <p className="card-title">Próximas Sessões</p>
      <div className="card-divider" />
      <div style={{ overflowX: "auto" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Data/Hora</th>
              <th>Cliente</th>
              <th>Tipo</th>
              <th>Duração</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {upcoming.map((session) => {
              const name = session.client_name ?? "—";
              const av = getAvatarVariant(name);
              const initials = name
                .split(" ")
                .map((w) => w[0])
                .join("")
                .slice(0, 2)
                .toUpperCase();

              return (
                <tr key={session.id}>
                  <td style={{ color: "var(--text-primary)" }}>
                    {formatDateTime(session.scheduled_at)}
                  </td>

                  <td>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8 }}
                    >
                      {/* Avatar circle */}
                      <div
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: "50%",
                          background: av.bg,
                          border: `1px solid ${av.border}`,
                          color: av.color,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 10,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {initials}
                      </div>
                      <span
                        style={{
                          fontWeight: 600,
                          color: "var(--text-primary)",
                          fontSize: 13,
                        }}
                      >
                        {name}
                      </span>
                    </div>
                  </td>

                  <td style={{ color: "var(--text-muted)" }}>Sessão</td>

                  <td style={{ color: "var(--text-muted)" }}>
                    {session.duration_minutes} min
                  </td>

                  <td>
                    <span className={STATUS_BADGE[session.status]}>
                      {STATUS_LABELS[session.status]}
                    </span>
                  </td>

                  <td>
                    <button
                      className="btn-secondary"
                      style={{ padding: "4px 12px", fontSize: 12 }}
                      onClick={() => onEditSession(session)}
                    >
                      Detalhes
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AgendaPage
// ---------------------------------------------------------------------------

export function AgendaPage() {
  const [currentWeek, setCurrentWeek] = useState<Date>(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>("week");
  const [formOpen, setFormOpen] = useState(false);
  const [editingSession, setEditingSession] = useState<Session | null>(null);
  const [defaultFormDate, setDefaultFormDate] = useState<Date | undefined>();

  // Fetch full month so calendar doesn't need extra requests when navigating
  // days within the same month.
  const monthParam = format(currentWeek, "yyyy-MM");
  const { data: sessions = [], isLoading } = useSessions({
    date: monthParam,
    limit: 100,
  });

  // Day view: filter already-loaded sessions for the selected day.
  const sessionsForDay = sessions.filter((s) =>
    isSameDay(parseISO(s.scheduled_at), currentWeek),
  );

  // ── Navigation ──────────────────────────────────────────────────────────

  function navigate(direction: "prev" | "next"): void {
    if (viewMode === "week") {
      setCurrentWeek((prev) =>
        direction === "prev" ? subWeeks(prev, 1) : addWeeks(prev, 1),
      );
    } else {
      setCurrentWeek((prev) =>
        direction === "prev" ? subDays(prev, 1) : addDays(prev, 1),
      );
    }
  }

  // ── Handlers ────────────────────────────────────────────────────────────

  function handleEditSession(session: Session): void {
    setEditingSession(session);
    setFormOpen(true);
  }

  function handleNewSession(date: Date): void {
    setDefaultFormDate(date);
    setFormOpen(true);
  }

  function handleFormOpenChange(open: boolean): void {
    setFormOpen(open);
    if (!open) {
      setEditingSession(null);
      setDefaultFormDate(undefined);
    }
  }

  // ── Header date label ────────────────────────────────────────────────────

  const headerDate =
    viewMode === "week"
      ? format(currentWeek, "MMMM yyyy", { locale: ptBR })
      : format(currentWeek, "d 'de' MMMM yyyy", { locale: ptBR });

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: 24, minHeight: "100vh" }}>
      {/* ── Page header ──────────────────────────────────────────────── */}
      <div
        className="animate-slide-up"
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2
            style={{
              fontFamily: "var(--font-heading)",
              fontWeight: 700,
              fontSize: 24,
              color: "var(--text-primary)",
              margin: 0,
            }}
          >
            Agenda
          </h2>
          <p
            style={{
              fontSize: 13,
              color: "var(--text-muted)",
              margin: "4px 0 0",
              textTransform: "capitalize",
            }}
          >
            {headerDate}
          </p>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {/* Week / Day toggle */}
          <div
            style={{
              display: "flex",
              gap: 2,
              padding: 3,
              background: "rgba(255,255,255,0.05)",
              borderRadius: 8,
              border: "1px solid var(--border-default)",
            }}
          >
            <button
              onClick={() => setViewMode("week")}
              style={{
                padding: "4px 14px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                border: "none",
                background:
                  viewMode === "week" ? "rgba(139,92,246,0.25)" : "transparent",
                color: viewMode === "week" ? "#c4b5fd" : "var(--text-muted)",
                transition: "all 0.15s",
              }}
            >
              Semana
            </button>
            <button
              onClick={() => setViewMode("day")}
              style={{
                padding: "4px 14px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                border: "none",
                background:
                  viewMode === "day" ? "rgba(139,92,246,0.25)" : "transparent",
                color: viewMode === "day" ? "#c4b5fd" : "var(--text-muted)",
                transition: "all 0.15s",
              }}
            >
              Dia
            </button>
          </div>

          {/* Navigation */}
          <button className="btn-secondary" onClick={() => navigate("prev")}>
            <ChevronLeft size={14} aria-hidden /> Anterior
          </button>

          <button
            className="btn-secondary"
            onClick={() => setCurrentWeek(new Date())}
          >
            Hoje
          </button>

          <button className="btn-secondary" onClick={() => navigate("next")}>
            Próximo <ChevronRight size={14} aria-hidden />
          </button>

          {/* New session */}
          <button
            className="btn-primary"
            onClick={() => {
              setEditingSession(null);
              setDefaultFormDate(undefined);
              setFormOpen(true);
            }}
          >
            <Plus
              size={14}
              aria-hidden
              style={{ marginRight: 4, verticalAlign: "middle" }}
            />
            Nova Sessão
          </button>
        </div>
      </div>

      {/* ── Calendar card ──────────────────────────────────────────────── */}
      <div
        className="glass-card bordered animate-slide-up animate-delay-1"
        style={{ padding: 0, marginBottom: 16, overflow: "hidden" }}
      >
        {isLoading ? (
          <div
            style={{
              padding: 48,
              textAlign: "center",
              fontSize: 13,
              color: "var(--text-muted)",
            }}
          >
            Carregando agenda…
          </div>
        ) : viewMode === "week" ? (
          <WeekView
            sessions={sessions}
            currentWeek={currentWeek}
            onSessionClick={handleEditSession}
            onNewSession={handleNewSession}
          />
        ) : (
          <DayList
            sessions={sessionsForDay}
            date={currentWeek}
            onSessionClick={handleEditSession}
          />
        )}
      </div>

      {/* ── Upcoming sessions table ────────────────────────────────────── */}
      <UpcomingSessionsTable
        sessions={sessions}
        onEditSession={handleEditSession}
      />

      {/* ── Session form dialog (unchanged) ────────────────────────────── */}
      <SessionForm
        open={formOpen}
        onOpenChange={handleFormOpenChange}
        session={editingSession}
        defaultDate={defaultFormDate}
      />
    </div>
  );
}
