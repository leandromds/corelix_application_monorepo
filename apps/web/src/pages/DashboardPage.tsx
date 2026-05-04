/**
 * DashboardPage — overview with today's sessions and quick navigation.
 *
 * This component renders inside AppShell's <Outlet />, so it doesn't
 * need to provide its own sidebar, topbar, or full-height wrappers.
 */

import { useNavigate } from "react-router-dom";
import { CalendarDays, Users, ArrowRight } from "lucide-react";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useAuth } from "@/hooks/useAuth";
import { useTodaySessions } from "@/features/agenda/hooks/useTodaySessions";
import { useUpcomingSessions } from "@/features/agenda/hooks/useUpcomingSessions";
import { useClients } from "@/features/clients/hooks/useClients";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Avatar } from "@/components/shared/Avatar";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function formatCurrency(value: string): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

function formatTime(iso: string): string {
  return format(parseISO(iso), "HH:mm");
}

// ---------------------------------------------------------------------------
// Quick-action card
// ---------------------------------------------------------------------------

interface QuickCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  href: string;
}

function QuickCard({ icon, title, description, href }: QuickCardProps) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(href)}
      style={{
        background: "white",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--border-default)",
        boxShadow: "var(--shadow-sm)",
        padding: "20px",
        textAlign: "left",
        cursor: "pointer",
        transition: "box-shadow 0.15s, transform 0.15s",
        width: "100%",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-card)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-sm)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
      }}
    >
      <div style={{ fontSize: 28, marginBottom: 12 }}>{icon}</div>
      <div
        style={{
          fontFamily: "var(--font-heading)",
          fontSize: 15,
          fontWeight: 700,
          color: "var(--text-primary)",
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
        {description}
      </p>
    </button>
  );
}

// ---------------------------------------------------------------------------
// DashboardPage
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const { professional } = useAuth();
  const navigate = useNavigate();

  const { data: todaySessions = [], isLoading: loadingToday } =
    useTodaySessions();
  const { data: upcomingSessions = [], isLoading: loadingUpcoming } =
    useUpcomingSessions();
  const { data: clients = [] } = useClients({ is_active: true });

  const firstName = professional?.full_name?.split(" ")[0] ?? "você";
  const todayFormatted = format(new Date(), "EEEE, d 'de' MMMM", {
    locale: ptBR,
  });

  const scheduledToday = todaySessions.filter(
    (s) => s.status === "scheduled",
  ).length;
  const completedToday = todaySessions.filter(
    (s) => s.status === "completed",
  ).length;

  const revenueToday = todaySessions
    .filter((s) => s.status === "completed")
    .reduce((sum, s) => sum + Number(s.price), 0);

  return (
    <div
      style={{
        padding: "24px",
        maxWidth: 1100,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}
    >
      {/* ──────────────────────────────────────────────────────────────────── */}
      {/* Welcome banner                                                        */}
      {/* ──────────────────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: 24,
              fontWeight: 800,
              color: "var(--text-primary)",
              margin: 0,
            }}
          >
            Bom dia, {firstName}! 👋
          </h1>
          <p
            style={{
              fontSize: 13,
              color: "var(--text-muted)",
              margin: "4px 0 0",
              textTransform: "capitalize",
            }}
          >
            {todayFormatted}
            {todaySessions.length > 0 &&
              ` · ${todaySessions.length} sessão${todaySessions.length > 1 ? "ões" : ""} hoje`}
          </p>
        </div>

        <Button
          size="sm"
          onClick={() => navigate("/agenda")}
          style={{ flexShrink: 0 }}
        >
          + Nova Sessão
        </Button>
      </div>

      {/* ──────────────────────────────────────────────────────────────────── */}
      {/* KPI cards                                                             */}
      {/* ──────────────────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 16,
        }}
      >
        {[
          {
            label: "📅 Sessões Hoje",
            value: todaySessions.length.toString(),
            sub: `${scheduledToday} agendada${scheduledToday !== 1 ? "s" : ""} · ${completedToday} realizada${completedToday !== 1 ? "s" : ""}`,
            color: "var(--text-primary)",
          },
          {
            label: "⏱️ Próximas",
            value: upcomingSessions.length.toString(),
            sub: "sessões agendadas",
            color: "var(--info)",
          },
          {
            label: "💰 Receita Hoje",
            value: formatCurrency(revenueToday.toString()),
            sub: "sessões realizadas",
            color: "var(--success)",
          },
          {
            label: "👥 Clientes Ativos",
            value: clients.length.toString(),
            sub: "cadastrados",
            color: "var(--text-primary)",
          },
        ].map((kpi) => (
          <div
            key={kpi.label}
            style={{
              background: "white",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--border-default)",
              boxShadow: "var(--shadow-sm)",
              padding: "18px 20px",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-muted)",
                marginBottom: 6,
              }}
            >
              {kpi.label}
            </div>
            <div
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: 28,
                fontWeight: 700,
                color: kpi.color,
                lineHeight: 1,
              }}
            >
              {kpi.value}
            </div>
            <div
              style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}
            >
              {kpi.sub}
            </div>
          </div>
        ))}
      </div>

      {/* ──────────────────────────────────────────────────────────────────── */}
      {/* Today's sessions                                                      */}
      {/* ──────────────────────────────────────────────────────────────────── */}
      <div
        style={{
          background: "white",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-default)",
          boxShadow: "var(--shadow-sm)",
          overflow: "hidden",
        }}
      >
        {/* Card header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-default)",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: 14,
              fontWeight: 700,
              color: "var(--text-primary)",
            }}
          >
            Agenda de Hoje
          </span>
          <button
            onClick={() => navigate("/agenda")}
            style={{
              background: "none",
              border: "none",
              fontSize: 13,
              color: "var(--info)",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            Ver agenda completa
            <ArrowRight style={{ width: 14, height: 14 }} aria-hidden />
          </button>
        </div>

        {/* Content */}
        {loadingToday ? (
          <div style={{ padding: "32px 20px", textAlign: "center" }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "12px 0",
                  borderBottom:
                    i < 2 ? "1px solid var(--border-default)" : "none",
                }}
              >
                <div
                  className="animate-pulse"
                  style={{
                    width: 40,
                    height: 12,
                    background: "var(--border-default)",
                    borderRadius: 4,
                  }}
                />
                <div
                  className="animate-pulse"
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: "var(--border-default)",
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div
                    className="animate-pulse"
                    style={{
                      width: 120,
                      height: 12,
                      background: "var(--border-default)",
                      borderRadius: 4,
                      marginBottom: 6,
                    }}
                  />
                  <div
                    className="animate-pulse"
                    style={{
                      width: 80,
                      height: 10,
                      background: "var(--border-default)",
                      borderRadius: 4,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : todaySessions.length === 0 ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "40px 20px",
              gap: 12,
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 36 }}>📅</div>
            <p
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: 15,
                fontWeight: 700,
                color: "var(--text-primary)",
                margin: 0,
              }}
            >
              Nenhuma sessão hoje
            </p>
            <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
              Sua agenda está livre. Que tal agendar uma sessão?
            </p>
            <Button size="sm" onClick={() => navigate("/agenda")}>
              + Agendar sessão
            </Button>
          </div>
        ) : (
          <div style={{ padding: "0 20px" }}>
            {todaySessions.map((session, idx) => (
              <div
                key={session.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "12px 0",
                  borderBottom:
                    idx < todaySessions.length - 1
                      ? "1px solid var(--border-default)"
                      : "none",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    width: 40,
                    flexShrink: 0,
                  }}
                >
                  {formatTime(session.scheduled_at)}
                </span>
                <Avatar
                  initials={(session.client_name ?? "CL")
                    .slice(0, 2)
                    .toUpperCase()}
                  color={getAvatarColor(session.client_name ?? "Cliente")}
                  size="sm"
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: "var(--text-primary)",
                    }}
                  >
                    {session.client_name ?? "Cliente"}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-muted)",
                      marginTop: 1,
                    }}
                  >
                    {session.duration_minutes} min ·{" "}
                    {formatCurrency(session.price)}
                  </div>
                </div>
                <StatusBadge status={session.status} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ──────────────────────────────────────────────────────────────────── */}
      {/* Quick actions                                                         */}
      {/* ──────────────────────────────────────────────────────────────────── */}
      <div>
        <p
          style={{
            fontSize: 11,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text-muted)",
            marginBottom: 12,
          }}
        >
          Acesso Rápido
        </p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
          }}
        >
          <QuickCard
            icon={
              <CalendarDays
                style={{ width: 28, height: 28, color: "var(--info)" }}
              />
            }
            title="Agenda"
            description="Visualize e gerencie suas sessões"
            href="/agenda"
          />
          <QuickCard
            icon={
              <Users
                style={{ width: 28, height: 28, color: "var(--success)" }}
              />
            }
            title="Clientes"
            description="Cadastre e gerencie seus clientes"
            href="/clients"
          />
        </div>
      </div>

      {/* Upcoming */}
      {!loadingUpcoming && upcomingSessions.length > 0 && (
        <div
          style={{
            background: "white",
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--border-default)",
            boxShadow: "var(--shadow-sm)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 20px",
              borderBottom: "1px solid var(--border-default)",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: 14,
                fontWeight: 700,
                color: "var(--text-primary)",
              }}
            >
              Próximas Sessões
            </span>
            <button
              onClick={() => navigate("/agenda")}
              style={{
                background: "none",
                border: "none",
                fontSize: 13,
                color: "var(--info)",
                fontWeight: 500,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              Ver todas
              <ArrowRight style={{ width: 14, height: 14 }} aria-hidden />
            </button>
          </div>
          <div style={{ padding: "0 20px" }}>
            {upcomingSessions.slice(0, 5).map((session, idx) => (
              <div
                key={session.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "12px 0",
                  borderBottom:
                    idx < Math.min(upcomingSessions.length, 5) - 1
                      ? "1px solid var(--border-default)"
                      : "none",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    color: "var(--text-muted)",
                    width: 80,
                    flexShrink: 0,
                    fontWeight: 500,
                  }}
                >
                  {format(parseISO(session.scheduled_at), "dd/MM HH:mm")}
                </span>
                <Avatar
                  initials={(session.client_name ?? "CL")
                    .slice(0, 2)
                    .toUpperCase()}
                  color={getAvatarColor(session.client_name ?? "Cliente")}
                  size="sm"
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: "var(--text-primary)",
                    }}
                  >
                    {session.client_name ?? "Cliente"}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {session.duration_minutes} min
                  </div>
                </div>
                <StatusBadge status={session.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
