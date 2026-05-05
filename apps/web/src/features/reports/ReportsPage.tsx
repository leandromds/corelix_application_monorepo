/**
 * ReportsPage — billing reports with KPI summary and AI insights.
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
 *      → TanStack Query refetches automatically when `billingParams` changes,
 *        so a second click with new dates just updates the key.
 *
 * All filter state lives here (not in PeriodFilter) so both hooks can share
 * the same derived params without prop-drilling callbacks through the child.
 */

import { useEffect, useState } from 'react'
import { format, subDays } from 'date-fns'

import { useReportSummary } from './hooks/useReportSummary'
import { useBillingReport }  from './hooks/useBillingReport'
import { KpiCard }           from './components/KpiCard'
import { PeriodFilter }      from './components/PeriodFilter'
import { BillingTable }      from './components/BillingTable'
import type { ReportParams } from './types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(amount: string): string {
  return new Intl.NumberFormat('pt-BR', {
    style:    'currency',
    currency: 'BRL',
  }).format(Number(amount))
}

function toDateString(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

// ---------------------------------------------------------------------------
// ReportsPage
// ---------------------------------------------------------------------------

export function ReportsPage() {
  // ── Filter state ──────────────────────────────────────────────────────

  // Lazy initialisers call new Date() at mount time, not at module parse time,
  // so vi.useFakeTimers({ toFake: ['Date'] }) in tests correctly anchors them.
  const [startDate, setStartDate] = useState<string>(() =>
    toDateString(subDays(new Date(), 30)),
  )
  const [endDate, setEndDate] = useState<string>(() =>
    toDateString(new Date()),
  )
  const [statusFilter, setStatusFilter] = useState<string[]>(['completed'])

  // ── Billing on-demand params ─────────────────────────────────────────
  // null  → billing query disabled (user hasn't clicked "Gerar Relatório")
  // value → query fires, key changes on each new submission
  const [billingParams, setBillingParams] = useState<ReportParams | null>(null)

  // ── Mount animation ──────────────────────────────────────────────────
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  // ── Data ──────────────────────────────────────────────────────────────

  const summaryParams: ReportParams = {
    start_date:    startDate,
    end_date:      endDate,
    status_filter: statusFilter,
  }

  const { data: summary, isLoading: summaryLoading } =
    useReportSummary(summaryParams)

  const {
    data:    billing,
    isLoading: billingLoading,
    isError:   billingError,
  } = useBillingReport(billingParams)

  // ── Handlers ─────────────────────────────────────────────────────────

  function handlePreset(days: number): void {
    const end   = new Date()
    const start = subDays(end, days)
    setEndDate(toDateString(end))
    setStartDate(toDateString(start))
  }

  function handleGenerateReport(): void {
    setBillingParams({
      start_date:    startDate,
      end_date:      endDate,
      status_filter: statusFilter,
    })
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        padding:    24,
        maxWidth:   1200,
        margin:     '0 auto',
        opacity:    mounted ? 1 : 0,
        transform:  mounted ? 'translateY(0)' : 'translateY(10px)',
        transition: 'opacity 0.25s ease, transform 0.25s ease',
      }}
    >
      {/* ── Page header ── */}
      <div style={{ marginBottom: 24 }}>
        <h2
          style={{
            fontFamily: 'var(--font-heading)',
            fontWeight: 700,
            fontSize:   24,
            color:      'var(--text-primary)',
            margin:     0,
          }}
        >
          Relatórios
        </h2>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: '4px 0 0' }}>
          Análise de faturamento por período
        </p>
      </div>

      {/* ── Filter panel ── */}
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

      {/* ── KPI summary cards ── */}
      <div
        style={{
          display:               'grid',
          gridTemplateColumns:   'repeat(auto-fill, minmax(220px, 1fr))',
          gap:                   16,
          marginBottom:          24,
        }}
      >
        <KpiCard
          label="Total de sessões"
          value={String(summary?.total_sessions ?? 0)}
          icon="📅"
          isLoading={summaryLoading}
        />
        <KpiCard
          label="Faturamento do período"
          value={formatCurrency(summary?.total_amount ?? '0')}
          icon="💰"
          isLoading={summaryLoading}
          valueColor="var(--color-primary)"
        />
        <KpiCard
          label="Período"
          value={
            summary
              ? `${summary.period_start} → ${summary.period_end}`
              : '—'
          }
          icon="📆"
          isLoading={summaryLoading}
        />
      </div>

      {/* ── Billing report section (on-demand) ── */}
      {billingParams !== null && (
        <div
          style={{
            background:   'var(--bg-surface-card)',
            borderRadius: 'var(--radius-lg)',
            border:       '1px solid var(--border-default)',
            boxShadow:    'var(--shadow-card)',
            overflow:     'hidden',
          }}
        >
          {/* Section header */}
          <div
            style={{
              display:         'flex',
              alignItems:      'center',
              justifyContent:  'space-between',
              padding:         '16px 20px',
              borderBottom:    '1px solid var(--border-default)',
            }}
          >
            <h3
              style={{
                fontFamily: 'var(--font-heading)',
                fontSize:   16,
                fontWeight: 700,
                color:      'var(--text-primary)',
                margin:     0,
              }}
            >
              Relatório Detalhado
            </h3>
            {billing && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {billing.total_sessions}{' '}
                {billing.total_sessions === 1 ? 'sessão' : 'sessões'}{' '}
                · {formatCurrency(billing.total_amount)}
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
                    height:       44,
                    background:   'var(--bg-surface)',
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
                padding:   '32px 24px',
                textAlign: 'center',
                color:     'var(--text-muted)',
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }} aria-hidden="true">⚠️</div>
              <p
                style={{
                  fontWeight: 600,
                  margin:     '0 0 4px',
                  color:      'var(--text-primary)',
                }}
              >
                Erro ao gerar relatório
              </p>
              <p style={{ fontSize: 13, margin: 0 }}>
                Verifique sua conexão e tente novamente.
              </p>
            </div>
          )}

          {/* Data: AI insights + billing table */}
          {!billingLoading && !billingError && billing && (
            <>
              {/* AI insights block — only shown when ai_insights is non-null */}
              {billing.ai_insights && (
                <div
                  style={{
                    margin:      '16px 20px 0',
                    padding:     '14px 16px',
                    background:  'var(--badge-ai-bg, rgba(99,102,241,0.08))',
                    borderRadius: 'var(--radius-md)',
                    border:      '1px solid rgba(99,102,241,0.2)',
                    display:     'flex',
                    gap:         10,
                    alignItems:  'flex-start',
                  }}
                >
                  <span style={{ fontSize: 18 }} aria-hidden="true">✨</span>
                  <div>
                    <p
                      style={{
                        fontSize:       11,
                        fontWeight:     700,
                        textTransform:  'uppercase',
                        letterSpacing:  '0.08em',
                        color:          'var(--badge-ai-fg, #6366f1)',
                        margin:         '0 0 4px',
                      }}
                    >
                      Insights da IA
                    </p>
                    <p
                      style={{
                        fontSize:   14,
                        color:      'var(--text-primary)',
                        margin:     0,
                        lineHeight: 1.6,
                      }}
                    >
                      {billing.ai_insights}
                    </p>
                  </div>
                </div>
              )}

              {/* Billing table */}
              <div style={{ marginTop: billing.ai_insights ? 16 : 0 }}>
                <BillingTable clients={billing.clients} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
