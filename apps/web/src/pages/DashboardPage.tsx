/**
 * DashboardPage — dark glass morphism overview dashboard.
 *
 * Layout
 *   1. Alert banner  — greeting + session count + unread messages
 *   2. KPI grid (4)  — Sessões Hoje · Msgs Pendentes · Receita Hoje · Ocupação
 *   3. Main grid     — Agenda de Hoje (1fr)  |  WhatsApp (300px)
 *   4. Charts grid   — Sessões por Período (2fr)  |  Receita da Semana (1fr)
 *
 * Data hooks
 *   useTodaySessions    — today's session list (loading state + empty state)
 *   useUpcomingSessions — upcoming sessions (used in Ocupação KPI sub-label)
 *   useReportSummary    — today + weekly revenue totals (two query instances)
 *   useConversations    — WhatsApp conversation list
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { format, parseISO, startOfWeek, endOfWeek } from "date-fns";
import { useAuth } from "@/hooks/useAuth";
import { useTodaySessions } from "@/features/agenda/hooks/useTodaySessions";
import { useUpcomingSessions } from "@/features/agenda/hooks/useUpcomingSessions";
import { useReportSummary } from "@/features/reports/hooks/useReportSummary";
import { useConversations } from "@/features/whatsapp/hooks/useConversations";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: string | number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

function formatTime(iso: string): string {
  return format(parseISO(iso), "HH:mm");
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return parts
    .slice(0, 2)
    .map((n) => n[0] ?? "")
    .join("")
    .toUpperCase();
}

// Shared avatar style per wireframe spec
const AVATAR: React.CSSProperties = {
  background: "rgba(139,92,246,0.25)",
  border: "1px solid rgba(139,92,246,0.4)",
  color: "hsl(270,95%,85%)",
  width: 28,
  height: 28,
  borderRadius: "50%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 10,
  fontWeight: 700,
  flexShrink: 0,
};

// session.status → CSS badge class
const STATUS_BADGE: Record<string, string> = {
  scheduled: "badge-pending",
  completed: "badge-confirmed",
  cancelled: "badge-cancelled",
  no_show: "badge-noshow",
};

// session.status → Portuguese label
const STATUS_LABEL: Record<string, string> = {
  scheduled: "Agendada",
  completed: "Realizada",
  cancelled: "Cancelada",
  no_show: "No-show",
};

// Static week bars — backend does not yet expose a weekly aggregation endpoint
const WEEK_BARS = [
  { label: "Seg", height: 65 },
  { label: "Ter", height: 45 },
  { label: "Qua", height: 80 },
  { label: "Qui", height: 55 },
  { label: "Sex", height: 90 },
  { label: "Sáb", height: 30 },
  { label: "Dom", height: 20 },
] as const;

// Fixed revenue goals (R$) — replace with professional settings when available
const DAILY_GOAL = 500;
const WEEKLY_GOAL = 2500;

// ---------------------------------------------------------------------------
// Skeleton row for loading states
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className="session-row">
      <div
        className="skeleton"
        style={{ width: 38, height: 10, flexShrink: 0 }}
      />
      <div
        className="skeleton"
        style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0 }}
      />
      <div
        style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}
      >
        <div className="skeleton" style={{ width: "55%", height: 11 }} />
        <div className="skeleton" style={{ width: "35%", height: 9 }} />
      </div>
      <div
        className="skeleton"
        style={{ width: 62, height: 20, borderRadius: 9999 }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// DashboardPage
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const { professional } = useAuth();
  const navigate = useNavigate();

  // Chart period toggle state
  const [chartPeriod, setChartPeriod] = useState<"Semana" | "Mês" | "Tri">(
    "Semana",
  );

  // Date strings for report queries (YYYY-MM-DD)
  const today = format(new Date(), "yyyy-MM-dd");
  const weekStart = format(
    startOfWeek(new Date(), { weekStartsOn: 1 }),
    "yyyy-MM-dd",
  );
  const weekEnd = format(
    endOfWeek(new Date(), { weekStartsOn: 1 }),
    "yyyy-MM-dd",
  );

  // ── Data hooks ────────────────────────────────────────────────────────────
  const { data: todaySessions = [], isLoading: loadingToday } =
    useTodaySessions();
  const { data: upcomingSessions = [] } = useUpcomingSessions();
  const { data: conversations = [], isLoading: loadingConversations } =
    useConversations();

  // Two independent instances of useReportSummary — today & this week
  const { data: reportToday } = useReportSummary({
    start_date: today,
    end_date: today,
    status_filter: ["completed"],
  });
  const { data: reportWeek } = useReportSummary({
    start_date: weekStart,
    end_date: weekEnd,
    status_filter: ["completed"],
  });

  // ── Derived values ────────────────────────────────────────────────────────
  const firstName = professional?.full_name?.split(" ")[0] ?? "você";
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";

  const scheduledToday = todaySessions.filter(
    (s) => s.status === "scheduled",
  ).length;
  const completedToday = todaySessions.filter(
    (s) => s.status === "completed",
  ).length;

  const pendingMsgs = conversations.filter(
    (c) => c.status === "waiting_professional",
  ).length;
  const activeMsgs = conversations.filter((c) => c.status === "active").length;
  const totalUnread = pendingMsgs + activeMsgs;

  const revenueToday = reportToday ? Number(reportToday.total_amount) : 0;
  const weekRevenue = reportWeek ? Number(reportWeek.total_amount) : 0;
  const weekSessionCount = reportWeek?.total_sessions ?? 0;

  const revenuePct =
    DAILY_GOAL > 0
      ? Math.min(Math.round((revenueToday / DAILY_GOAL) * 100), 100)
      : 0;
  const weekRevenuePct =
    WEEKLY_GOAL > 0
      ? Math.min(Math.round((weekRevenue / WEEKLY_GOAL) * 100), 100)
      : 0;

  // Occupancy: non-cancelled slots vs estimated day capacity
  const activeSlots = todaySessions.filter(
    (s) => s.status !== "cancelled",
  ).length;
  const estimatedMax = Math.max(activeSlots + 2, 4);
  const freeSlots = estimatedMax - activeSlots;
  const occupancyPct =
    todaySessions.length === 0
      ? 0
      : Math.round((activeSlots / estimatedMax) * 100);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        padding: "24px",
        maxWidth: 1100,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 20,
      }}
    >
      {/* ── 1. Alert banner ───────────────────────────────────────────────── */}
      <div className="alert alert-purple animate-fade-in" style={{ gap: 12 }}>
        <span style={{ fontSize: 18, flexShrink: 0 }}>👋</span>

        <span style={{ flex: 1, lineHeight: 1.5 }}>
          <strong>
            {greeting}, {firstName}!
          </strong>{" "}
          Você tem{" "}
          <strong>
            {todaySessions.length} sess
            {todaySessions.length !== 1 ? "ões" : "ão"}
          </strong>{" "}
          hoje.
          {totalUnread > 0 && (
            <span style={{ color: "var(--warning)", marginLeft: 8 }}>
              · {totalUnread} mensagem{totalUnread !== 1 ? "s" : ""} não lida
              {totalUnread !== 1 ? "s" : ""}
            </span>
          )}
        </span>

        <button className="btn-link" onClick={() => navigate("/agenda")}>
          Ver →
        </button>
      </div>

      {/* ── 2. KPI Grid ───────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 14,
        }}
      >
        {/* KPI 1 — Sessões Hoje */}
        <div className="glass-card animate-slide-up">
          <div className="kpi-label">Sessões Hoje</div>
          <div
            className="kpi-value"
            style={{
              background: "linear-gradient(90deg,hsl(270,95%,80%),white)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            {todaySessions.length}
          </div>
          <div className="kpi-sub">
            {scheduledToday} confirmada{scheduledToday !== 1 ? "s" : ""} ·{" "}
            {completedToday} realizada{completedToday !== 1 ? "s" : ""}
          </div>
        </div>

        {/* KPI 2 — Msgs Pendentes */}
        <div className="glass-card animate-slide-up animate-delay-1">
          <div className="kpi-label">Msgs Pendentes</div>
          <div className="kpi-value" style={{ color: "var(--warning)" }}>
            {totalUnread}
          </div>
          <div className="kpi-sub" style={{ color: "var(--warning)" }}>
            {pendingMsgs} aguardando resposta
          </div>
        </div>

        {/* KPI 3 — Receita Hoje */}
        <div className="glass-card animate-slide-up animate-delay-2">
          <div className="kpi-label">Receita Hoje</div>
          <div className="kpi-value" style={{ color: "var(--success)" }}>
            {formatCurrency(revenueToday)}
          </div>
          <div className="progress-track" style={{ margin: "8px 0 5px" }}>
            <div
              className="progress-fill"
              style={{ width: `${revenuePct}%` }}
            />
          </div>
          <div className="kpi-sub">
            Meta: {formatCurrency(DAILY_GOAL)} · {revenuePct}%
          </div>
        </div>

        {/* KPI 4 — Ocupação */}
        <div className="glass-card animate-slide-up animate-delay-3">
          <div className="kpi-label">Ocupação</div>
          <div className="kpi-value" style={{ color: "var(--info)" }}>
            {occupancyPct}%
          </div>
          <div className="kpi-sub">
            {freeSlots} horário{freeSlots !== 1 ? "s" : ""} livre
            {freeSlots !== 1 ? "s" : ""} · {upcomingSessions.length} próxima
            {upcomingSessions.length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

      {/* ── 3. Main Grid: Agenda + WhatsApp ───────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 300px",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* ── Agenda de Hoje ────────────────────────────────────────────── */}
        <div className="glass-card bordered">
          {/* Header row */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 4,
            }}
          >
            <span className="card-title">📅 Agenda de Hoje</span>

            {/* Date navigation — all navigate to /agenda for now */}
            <div style={{ display: "flex", gap: 5 }}>
              <button
                className="btn-secondary"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => navigate("/agenda")}
              >
                ‹ Ant
              </button>
              <button
                className="btn-primary"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => navigate("/agenda")}
              >
                Hoje
              </button>
              <button
                className="btn-secondary"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => navigate("/agenda")}
              >
                Prox ›
              </button>
            </div>
          </div>

          <hr className="card-divider" />

          {/* Loading skeleton */}
          {loadingToday && (
            <>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </>
          )}

          {/* Empty state */}
          {!loadingToday && todaySessions.length === 0 && (
            <div className="empty-state" style={{ padding: "28px 0" }}>
              <div className="empty-icon">📅</div>
              <div className="empty-title">Nenhuma sessão hoje</div>
              <div className="empty-desc">
                Sua agenda está livre. Que tal agendar uma sessão?
              </div>
              <button
                className="btn-primary"
                style={{ marginTop: 14 }}
                onClick={() => navigate("/agenda")}
              >
                + Agendar sessão
              </button>
            </div>
          )}

          {/* Session list */}
          {!loadingToday && todaySessions.length > 0 && (
            <>
              {todaySessions.map((session) => (
                <div key={session.id} className="session-row">
                  <span className="session-time">
                    {formatTime(session.scheduled_at)}
                  </span>

                  <div style={AVATAR}>
                    {getInitials(session.client_name ?? "CL")}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="session-name">
                      {session.client_name ?? "Cliente"}
                    </div>
                    <div className="session-desc">
                      {session.duration_minutes} min ·{" "}
                      {formatCurrency(session.price)}
                    </div>
                  </div>

                  <span
                    className={STATUS_BADGE[session.status] ?? "badge-pending"}
                  >
                    {STATUS_LABEL[session.status] ?? session.status}
                  </span>
                </div>
              ))}

              <div style={{ marginTop: 14, textAlign: "right" }}>
                <button
                  className="btn-link"
                  onClick={() => navigate("/agenda")}
                >
                  Ver agenda completa →
                </button>
              </div>
            </>
          )}
        </div>

        {/* ── WhatsApp ──────────────────────────────────────────────────── */}
        <div className="glass-card bordered">
          {/* Header row */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 4,
            }}
          >
            {/* WhatsApp icon — green message bubble */}
            <span style={{ fontSize: 16, lineHeight: 1 }}>💬</span>
            <span className="card-title" style={{ flex: 1, marginBottom: 0 }}>
              WhatsApp
            </span>
            {conversations.length > 0 && (
              <span className="badge-ai">{conversations.length}</span>
            )}
          </div>

          <hr className="card-divider" />

          {/* Loading skeleton */}
          {loadingConversations && (
            <>
              {[0, 1, 2].map((i) => (
                <div key={i} className="wa-item">
                  <div
                    className="skeleton"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: "50%",
                      flexShrink: 0,
                    }}
                  />
                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div
                      className="skeleton"
                      style={{ width: "65%", height: 11 }}
                    />
                    <div
                      className="skeleton"
                      style={{ width: "85%", height: 9 }}
                    />
                  </div>
                </div>
              ))}
            </>
          )}

          {/* Empty state */}
          {!loadingConversations && conversations.length === 0 && (
            <div className="empty-state" style={{ padding: "20px 0" }}>
              <div className="empty-icon">💬</div>
              <div className="empty-title">Sem conversas</div>
              <div className="empty-desc">
                Nenhuma conversa ativa no momento
              </div>
            </div>
          )}

          {/* Conversation list */}
          {!loadingConversations && conversations.length > 0 && (
            <>
              {conversations.slice(0, 5).map((conv) => {
                const badgeClass =
                  conv.status === "active"
                    ? "badge-ai"
                    : conv.status === "waiting_professional"
                      ? "badge-pending"
                      : "badge-noshow";

                const badgeLabel =
                  conv.status === "active"
                    ? "IA"
                    : conv.status === "waiting_professional"
                      ? "Pendente"
                      : "Resolvido";

                return (
                  <div key={conv.id} className="wa-item">
                    {/* Avatar — last 2 digits of phone as initials */}
                    <div
                      style={{
                        ...AVATAR,
                        width: 32,
                        height: 32,
                        fontSize: 11,
                      }}
                    >
                      {conv.client_phone.replace(/\D/g, "").slice(-2)}
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="wa-name">
                        <span
                          style={{
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {conv.client_phone}
                        </span>
                        <span className="wa-time">
                          {format(parseISO(conv.last_message_at), "HH:mm")}
                        </span>
                      </div>
                      <div className="wa-preview">
                        <span className={badgeClass}>{badgeLabel}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {/* Footer */}
          <hr className="card-divider" style={{ marginTop: 12 }} />
          <p
            style={{
              fontSize: 10,
              color: "var(--text-subtle)",
              marginBottom: 8,
              lineHeight: 1.5,
            }}
          >
            Respostas automáticas via IA ativas
          </p>
          <button className="btn-link" onClick={() => navigate("/whatsapp")}>
            Abrir WhatsApp →
          </button>
        </div>
      </div>

      {/* ── 4. Charts Grid ────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr",
          gap: 20,
          alignItems: "start",
        }}
      >
        {/* ── Bar chart — Sessões por Período ───────────────────────────── */}
        <div className="glass-card bordered">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 4,
            }}
          >
            <span className="card-title">📊 Sessões por Período</span>

            {/* Period toggle */}
            <div style={{ display: "flex", gap: 4 }}>
              {(["Semana", "Mês", "Tri"] as const).map((p) => (
                <button
                  key={p}
                  className={
                    chartPeriod === p ? "btn-primary" : "btn-secondary"
                  }
                  style={{ padding: "3px 10px", fontSize: 11 }}
                  onClick={() => setChartPeriod(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <hr className="card-divider" />

          {/*
           * Bar chart — heights are pixel values matching a 100px container.
           * bar-chart uses align-items: flex-end so all bars grow upward from
           * the same baseline; bar-label sits below each column.
           * NOTE: weekly aggregation endpoint not yet implemented — using
           * static placeholder data (see WEEK_BARS constant above).
           */}
          <div className="bar-chart" style={{ height: 100, marginTop: 16 }}>
            {WEEK_BARS.map(({ label, height }) => (
              <div key={label} className="bar-group">
                <div className="bar" style={{ height }} />
                <div className="bar-label">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Receita da Semana ─────────────────────────────────────────── */}
        <div className="glass-card glow bordered">
          <div className="kpi-label" style={{ marginBottom: 10 }}>
            Receita da Semana
          </div>

          <div
            className="kpi-value"
            style={{ color: "var(--success)", fontSize: 26 }}
          >
            {formatCurrency(weekRevenue)}
          </div>

          <div className="kpi-sub" style={{ marginBottom: 10 }}>
            {weekSessionCount} sess{weekSessionCount !== 1 ? "ões" : "ão"}{" "}
            realizada{weekSessionCount !== 1 ? "s" : ""}
          </div>

          <div className="progress-track" style={{ marginBottom: 5 }}>
            <div
              className="progress-fill"
              style={{ width: `${weekRevenuePct}%` }}
            />
          </div>
          <div className="kpi-sub" style={{ marginBottom: 16 }}>
            Meta: {formatCurrency(WEEKLY_GOAL)} · {weekRevenuePct}%
          </div>

          <hr className="card-divider" />

          {/* Legend dots */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 9,
              marginTop: 6,
            }}
          >
            {[
              {
                color: "var(--success)",
                label: "Realizadas hoje",
                value: completedToday,
              },
              {
                color: "var(--warning)",
                label: "Agendadas hoje",
                value: scheduledToday,
              },
              {
                color: "hsl(270,95%,70%)",
                label: "Total na semana",
                value: weekSessionCount,
              },
            ].map(({ color, label, value }) => (
              <div
                key={label}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: color,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{ fontSize: 11, color: "var(--text-muted)", flex: 1 }}
                >
                  {label}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
