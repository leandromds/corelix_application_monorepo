/**
 * Integration tests for ReportsPage.
 *
 * Fake timers (Date only) anchor "today" to 2025-07-21 so that:
 *   - Default start_date (today − 30 days) = 2025-06-21  (stable)
 *   - Default end_date   (today)           = 2025-07-21  (stable)
 *   - Preset computations are deterministic
 *
 * Because only Date is faked (not setTimeout/setInterval), userEvent.setup()
 * works normally — no need for fireEvent workaround (gotcha: vi.useFakeTimers()
 * full mode breaks userEvent; partial mode with toFake:['Date'] does not).
 *
 * MSW mocks:
 *   GET /reports/summary → auto-fetched on mount (lightweight KPI data)
 *   GET /reports/billing → on-demand after clicking "Gerar Relatório"
 */

// Hoist mock — sonner is not used in reports hooks but mock avoids any
// "act()" warnings if a future component import pulls it transitively.
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { http, HttpResponse } from 'msw'
import userEvent from '@testing-library/user-event'

import { server, BASE_URL } from '@/test/server'
import { renderWithProviders, screen, waitFor } from '@/test/utils'
import { ReportsPage } from './ReportsPage'
import type { BillingReport, PeriodSummary } from './types'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_SUMMARY: PeriodSummary = {
  period_start: '2025-06-21',
  period_end: '2025-07-21',
  total_sessions: 12,
  total_amount: '1800.00',
  status_filter: ['completed'],
}

const MOCK_BILLING: BillingReport = {
  period_start: '2025-06-21',
  period_end: '2025-07-21',
  total_sessions: 12,
  total_amount: '1800.00',
  clients: [
    {
      client_id: 'c1',
      client_name: 'Ana Lima',
      session_count: 3,
      total_amount: '450.00',
      sessions: [
        {
          session_id: 's1',
          client_id: 'c1',
          client_name: 'Ana Lima',
          scheduled_at: '2025-07-10T10:00:00.000Z',
          duration_minutes: 50,
          price: '150.00',
          status: 'completed',
          notes: null,
        },
      ],
    },
  ],
  ai_insights: 'Seu faturamento cresceu 20% este mês.',
  generated_at: '2025-07-21T12:00:00.000Z',
}

// ---------------------------------------------------------------------------
// Lifecycle — fake Date only, keep timers real
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2025, 6, 21)) // local midnight July 21 2025

  server.use(
    http.get(BASE_URL + '/reports/summary', () => HttpResponse.json(MOCK_SUMMARY)),
    http.get(BASE_URL + '/reports/billing', () => HttpResponse.json(MOCK_BILLING)),
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ReportsPage', () => {
  // ── Render ─────────────────────────────────────────────────────────────

  it('renderiza o cabeçalho "Relatórios"', () => {
    renderWithProviders(<ReportsPage />)
    expect(screen.getByRole('heading', { name: /relatórios/i })).toBeInTheDocument()
  })

  // ── Summary KPI cards (auto-fetched) ────────────────────────────────────

  it('exibe KPI cards com dados do summary após auto-fetch', async () => {
    renderWithProviders(<ReportsPage />)

    // total_sessions = 12 — appears as text in the KPI card
    expect(await screen.findByText('12')).toBeInTheDocument()

    // total_amount formatted as BRL → "R$ 1.800,00"
    expect(screen.getByText(/1\.800/)).toBeInTheDocument()
  })

  it('exibe skeleton de carregamento antes do summary chegar', () => {
    // Handler never resolves → component stays in isLoading=true
    server.use(
      http.get(BASE_URL + '/reports/summary', async () => {
        await new Promise(() => {}) // intentional hang
        return HttpResponse.json(MOCK_SUMMARY)
      }),
    )

    renderWithProviders(<ReportsPage />)

    // KpiCardSkeleton renders with className="animate-pulse"
    const pulsingEls = document.querySelectorAll('.animate-pulse')
    expect(pulsingEls.length).toBeGreaterThan(0)
  })

  // ── Billing report (on-demand) ──────────────────────────────────────────

  it('exibe tabela de faturamento após clicar em "Gerar Relatório"', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))

    // Client name and total appear in the billing table
    expect(await screen.findByText('Ana Lima')).toBeInTheDocument()
    // Client total: R$ 450,00
    expect(screen.getByText(/R\$\s*450/)).toBeInTheDocument()
  })

  it('exibe insights de IA quando ai_insights está preenchido', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))

    // MOCK_BILLING.ai_insights contains "faturamento cresceu"
    expect(await screen.findByText(/faturamento cresceu/i)).toBeInTheDocument()
  })

  it('NÃO exibe seção de insights quando ai_insights é null', async () => {
    server.use(
      http.get(BASE_URL + '/reports/billing', () =>
        HttpResponse.json({ ...MOCK_BILLING, ai_insights: null }),
      ),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))
    // Wait until billing data is rendered (table has client rows)
    await screen.findByText('Ana Lima')

    // The "Insights da IA" label must not be in the DOM
    expect(screen.queryByText(/insights da ia/i)).not.toBeInTheDocument()
  })

  it('exibe empty state quando não há sessões no período', async () => {
    server.use(
      http.get(BASE_URL + '/reports/billing', () =>
        HttpResponse.json({
          ...MOCK_BILLING,
          clients: [],
          total_sessions: 0,
          total_amount: '0.00',
          ai_insights: null,
        }),
      ),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))

    expect(
      await screen.findByText(/nenhuma sessão encontrada/i),
    ).toBeInTheDocument()
  })

  // ── Period presets ──────────────────────────────────────────────────────

  it('preset "Últimos 7 dias" atualiza o campo de data de início', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /7 dias/i }))

    // today = 2025-07-21 → start = 2025-07-14
    const startInput = screen.getByLabelText(/data de início/i) as HTMLInputElement
    expect(startInput.value).toBe('2025-07-14')
  })

  it('preset "Últimos 30 dias" restaura start_date após mudança por outro preset', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    // First switch to 7-day window, then back to 30
    await user.click(screen.getByRole('button', { name: /7 dias/i }))
    await user.click(screen.getByRole('button', { name: /30 dias/i }))

    const startInput = screen.getByLabelText(/data de início/i) as HTMLInputElement
    // today = 2025-07-21 → start = 2025-06-21
    expect(startInput.value).toBe('2025-06-21')
  })

  // ── Expand / collapse ───────────────────────────────────────────────────

  it('expande linha do cliente para mostrar sessões individuais', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))
    await screen.findByText('Ana Lima')

    // Sessions row NOT visible before expand
    expect(screen.queryByText(/50 min/)).not.toBeInTheDocument()

    // Expand
    await user.click(
      screen.getByRole('button', { name: /expandir sessões de ana lima/i }),
    )

    // Session duration and price appear
    expect(screen.getByText(/50 min/)).toBeInTheDocument()
    expect(screen.getByText(/R\$\s*150/)).toBeInTheDocument()
  })

  it('colapsa sessões após segundo clique no botão de expansão', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))
    await screen.findByText('Ana Lima')

    // Expand
    await user.click(
      screen.getByRole('button', { name: /expandir sessões de ana lima/i }),
    )
    expect(screen.getByText(/50 min/)).toBeInTheDocument()

    // Collapse — aria-label flips to "Colapsar" when expanded
    await user.click(
      screen.getByRole('button', { name: /colapsar sessões de ana lima/i }),
    )
    await waitFor(() => {
      expect(screen.queryByText(/50 min/)).not.toBeInTheDocument()
    })
  })

  // ── Error state ─────────────────────────────────────────────────────────

  it('exibe mensagem de erro quando API de billing retorna 500', async () => {
    server.use(
      http.get(BASE_URL + '/reports/billing', () =>
        HttpResponse.json({ message: 'Internal Server Error' }, { status: 500 }),
      ),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />)

    await user.click(screen.getByRole('button', { name: /gerar relatório/i }))

    expect(
      await screen.findByText(/erro ao gerar relatório/i),
    ).toBeInTheDocument()
  })
})
