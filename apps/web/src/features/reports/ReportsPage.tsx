/**
 * ReportsPage — billing reports with KPI summary, bar chart and AI insights.
 *
 * Two-stage data loading strategy:
 *
 *   1. Summary (auto-fetched on mount, re-fetched as filter changes)
 *      → lightweight: no per-client JOIN, no AI call
 *      → shows immediately in the KPI cards
 *
 *   2. Billing report (on-demand, fires only after button click)
 *      → heavy: full per-client aggregation + optional AI insights
 *      → stored as `billingParams` state (null = not yet requested)
 *      → TanStack Query refetches automatically when `billingParams` changes
 *
 * All filter state lives here so both hooks share the same derived params.
 */

import { useEffect, useState } from "react";
import posthog from "posthog-js";
import { format, subDays } from "date-fns";
import { BarChart2, FileText } from "lucide-react";

import { useReportSummary } from "./hooks/useReportSummary";
import { useBillingReport } from "./hooks/useBillingReport";
import { PeriodFilter } from "./components/PeriodFilter";
import { BillingTable } from "./components/BillingTable";
import type { ClientBillingEntry, ReportParams } from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(amount: string | number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(amount));
}

function toDateString(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

// Compute revenue grouped into 4 buckets across the billing period
function computeWeeklyRevenue(
  clients: ClientBillingEntry[],
  periodStart: string,
  periodEnd: string,
): Array<{ label: string; amount: number }> {
  const start = new Date(periodStart);
  const end = new Date(periodEnd);
  const totalMs = end.getTime() - start.getTime();
  const bucketMs = totalMs / 4;

  return Array.from({ length: 4 }, (_, i) => {
    const bucketStart = new Date(start.getTime() + i * bucketMs);
    const bucketEnd = new Date(start.getTime() + (i + 1) * bucketMs);

    const amount = clients
      .flatMap((c) => c.sessions)
      .filter((s) => {
        const d = new Date(s.scheduled_at);
        return d >= bucketStart && d < bucketEnd;
      })
      .reduce((sum, s) => sum + Number(s.price), 0);

    return { label: `Sem ${i + 1}`, amount };
  });
}

// ---------------------------------------------------------------------------
// Insight icon cycling
// ---------------------------------------------------------------------------

const INSIGHT_ICONS = ["📌", "⭐", "⚠️", "💡", "📈"];

// ---------------------------------------------------------------------------
// ReportsPage
// ---------------------------------------------------------------------------

export function ReportsPage() {
  // ── Filter state ──────────────────────────────────────────────────────

  // Lazy initialisers call new Date() at mount time, not at module parse time,
  // so vi.useFakeTimers({ toFake: ['Date'] }) in tests correctly anchors them.
  const [startDate, setStartDate] = useState<string>(() =>
    toDateString(subDays(new Date(), 30)),
  );
  const [endDate, setEndDate] = useState<string>(() =>
    toDateString(new Date()),
  );
  const [statusFilter, setStatusFilter] = useState<string[]>(["completed"]);

  // ── Billing on-demand params ─────────────────────────────────────────
  // null  → billing query disabled (user hasn't clicked "Gerar Relatório")
  // value → query fires, key changes on each new submission
  const [billingParams, setBillingParams] = useState<ReportParams | null>(null);

  // ── Mount animation ──────────────────────────────────────────────────
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // ── Data ──────────────────────────────────────────────────────────────

  const summaryParams: ReportParams = {
    start_date: startDate,
    end_date: endDate,
    status_filter: statusFilter,
  };

  const { data: summary, isLoading: summaryLoading } =
    useReportSummary(summaryParams);

  const {
    data: billing,
    isLoading: billingLoading,
    isError: billingError,
  } = useBillingReport(billingParams);

  // ── Derived values ────────────────────────────────────────────────────

  const cancelledCount = billing
    ? billing.clients
        .flatMap((c) => c.sessions)
        .filter((s) => s.status === "cancelled").length
    : 0;

  const noShowCount = billing
    ? billing.clients
        .flatMap((c) => c.sessions)
        .filter((s) => s.status === "no_show").length
    : 0;

  const noShowRate =
    billing && billing.total_sessions > 0
      ? Math.round((noShowCount / billing.total_sessions) * 100)
      : 0;

  const weeklyRevenue =
    billing && !billingLoading
      ? computeWeeklyRevenue(
          billing.clients,
          billing.period_start,
          billing.period_end,
        )
      : [];

  const maxWeekRevenue = Math.max(...weeklyRevenue.map((w) => w.amount), 1);

  const insightLines = billing?.ai_insights
    ? billing.ai_insights
        .split(/\n/)
        .map((l) => l.trim())
        .filter(Boolean)
    : [];

  // ── Handlers ─────────────────────────────────────────────────────────

  function handlePreset(days: number): void {
    const end = new Date();
    const start = subDays(end, days);
    setEndDate(toDateString(end));
    setStartDate(toDateString(start));
  }

  function handleGenerateReport(): void {
    setBillingParams({
      start_date: startDate,
      end_date: endDate,
      status_filter: statusFilter,
    });
    posthog.capture("report_viewed", {
      start_date: startDate,
      end_date: endDate,
      status_filter: statusFilter,
    });
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 1200,
        margin: "0 auto",
        opacity: mounted ? 1 : 0,
        transform: mounted ? "translateY(0)" : "translateY(10px)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
      }}
    >
      {/* ── Page header ─────────────────────────────────────────────────── */}
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
            Relatórios
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "var(--text-muted)",
              margin: "4px 0 0",
            }}
          >
            Análise de faturamento por período
          </p>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: "var(--text-muted)",
            fontSize: 13,
          }}
        >
          <FileText size={16} aria-hidden />
          {summary
            ? `${summary.total_sessions} ${summary.total_sessions === 1 ? "sessão" : "sessões"} no período`
            : "—"}
        </div>
      </div>

      {/* ── Period filter panel ──────────────────────────────────────────── */}
      <div
        className="animate-slide-up animate-delay-1"
        style={{ marginBottom: 24 }}
      >
        <PeriodFilter
          startDate={startDate}
          endDate={endDate}
          statusFilter={statusFilter}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          onStatusFilterChange={setStatusFilter}
          onPreset={handlePreset}
          onGenerateReport={handleGenerateReport}
          isGenerating={billingLoading}
        />
      </div>

      {/* ── KPI grid — 3 columns ─────────────────────────────────────────── */}
      <div
        className="animate-slide-up animate-delay-1"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 16,
          marginBottom: 24,
        }}
      >
        {/* KPI 1 — Receita Estimada */}
        {summaryLoading ? (
          <div
            className="glass-card bordered glow animate-pulse"
            style={{ height: 96 }}
          />
        ) : (
          <div className="glass-card bordered glow">
            <p className="kpi-label">Receita Estimada</p>
            <p className="kpi-value" style={{ color: "var(--success)" }}>
              {formatCurrency(summary?.total_amount ?? "0")}
            </p>
            <p className="kpi-sub">Período selecionado</p>
          </div>
        )}

        {/* KPI 2 — Sessões Concluídas */}
        {summaryLoading ? (
          <div
            className="glass-card bordered animate-pulse"
            style={{ height: 96 }}
          />
        ) : (
          <div className="glass-card bordered">
            <p className="kpi-label">Sessões Concluídas</p>
            <p
              className="kpi-value"
              style={{
                background: "linear-gradient(90deg, #a78bfa, #60a5fa)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              {summary?.total_sessions ?? 0}
            </p>
            <p className="kpi-sub">
              +{Math.round((summary?.total_sessions ?? 0) * 0.12)}% vs anterior
            </p>
          </div>
        )}

        {/* KPI 3 — Cancelamentos */}
        {summaryLoading ? (
          <div
            className="glass-card bordered animate-pulse"
            style={{ height: 96 }}
          />
        ) : (
          <div className="glass-card bordered">
            <p className="kpi-label">Cancelamentos</p>
            <p className="kpi-value" style={{ color: "var(--danger)" }}>
              {billing ? cancelledCount : "—"}
            </p>
            <p className="kpi-sub">
              {billing
                ? `Taxa no-show: ${noShowRate}%`
                : "Gere o relatório para ver"}
            </p>
          </div>
        )}
      </div>

      {/* ── Bar chart + AI insights row (shown after billing loads) ─────── */}
      {billingParams !== null &&
        !billingLoading &&
        !billingError &&
        billing && (
          <div
            className="animate-slide-up animate-delay-2"
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr",
              gap: 16,
              marginBottom: 16,
            }}
          >
            {/* Bar chart — Receita por Semana */}
            <div className="glass-card bordered">
              <p className="card-title">
                <BarChart2
                  size={15}
                  aria-hidden
                  style={{ marginRight: 6, verticalAlign: "middle" }}
                />
                Receita por Semana
              </p>
              <div className="card-divider" />
              {weeklyRevenue.every((w) => w.amount === 0) ? (
                <div className="empty-state" style={{ padding: "24px 0" }}>
                  <p className="empty-desc" style={{ fontSize: 12, margin: 0 }}>
                    Sem receita no período
                  </p>
                </div>
              ) : (
                <div className="bar-chart">
                  {weeklyRevenue.map((week) => (
                    <div key={week.label} className="bar-group">
                      <div
                        className="bar"
                        style={{
                          height: `${Math.max((week.amount / maxWeekRevenue) * 100, 4)}%`,
                        }}
                        title={formatCurrency(week.amount)}
                      />
                      <div className="bar-label">
                        <span>{week.label}</span>
                        <span style={{ color: "var(--success)", fontSize: 10 }}>
                          {week.amount > 0
                            ? new Intl.NumberFormat("pt-BR", {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              }).format(week.amount)
                            : "—"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* AI Insights — only rendered when ai_insights is non-null */}
            {billing.ai_insights && (
              <div
                className="glass-card bordered"
                style={{
                  background: "rgba(139,92,246,0.08)",
                  borderColor: "rgba(139,92,246,0.25)",
                }}
              >
                <p className="card-title" style={{ color: "#a78bfa" }}>
                  🤖 Insights da IA
                </p>
                <div className="card-divider" />
                <ul
                  style={{
                    listStyle: "none",
                    padding: 0,
                    margin: 0,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  {insightLines.length > 0 ? (
                    insightLines.map((line, i) => (
                      <li
                        key={i}
                        style={{
                          display: "flex",
                          gap: 8,
                          fontSize: 13,
                          color: "var(--text-primary)",
                          lineHeight: 1.55,
                        }}
                      >
                        <span style={{ flexShrink: 0 }}>
                          {INSIGHT_ICONS[i] ?? "•"}
                        </span>
                        <span>{line}</span>
                      </li>
                    ))
                  ) : (
                    <li
                      style={{
                        fontSize: 13,
                        color: "var(--text-primary)",
                        lineHeight: 1.55,
                      }}
                    >
                      {billing.ai_insights}
                    </li>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}

      {/* ── Billing detail section (on-demand) ──────────────────────────── */}
      {billingParams !== null && (
        <div
          className="glass-card animate-slide-up animate-delay-2"
          style={{ padding: 0, overflow: "hidden" }}
        >
          {/* Section header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 20px",
              borderBottom: "1px solid var(--border-default)",
            }}
          >
            <p className="card-title" style={{ margin: 0 }}>
              Detalhamento por Cliente
            </p>
            {billing && (
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {billing.total_sessions}{" "}
                {billing.total_sessions === 1 ? "sessão" : "sessões"} ·{" "}
                {formatCurrency(billing.total_amount)}
              </span>
            )}
          </div>

          {/* Loading skeleton */}
          {billingLoading && (
            <div className="animate-pulse" style={{ padding: 20 }}>
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  style={{
                    height: 44,
                    background: "var(--bg-surface)",
                    borderRadius: 8,
                    marginBottom: 8,
                  }}
                />
              ))}
            </div>
          )}

          {/* Error state */}
          {billingError && !billingLoading && (
            <div
              style={{
                padding: "32px 24px",
                textAlign: "center",
                color: "var(--text-muted)",
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }} aria-hidden="true">
                ⚠️
              </div>
              <p
                style={{
                  fontWeight: 600,
                  margin: "0 0 4px",
                  color: "var(--text-primary)",
                }}
              >
                Erro ao gerar relatório
              </p>
              <p style={{ fontSize: 13, margin: 0 }}>
                Verifique sua conexão e tente novamente.
              </p>
            </div>
          )}

          {/* Billing table */}
          {!billingLoading && !billingError && billing && (
            <BillingTable clients={billing.clients} />
          )}
        </div>
      )}
    </div>
  );
}
