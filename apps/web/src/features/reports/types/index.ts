/**
 * Reports types — mirrors backend reports/schemas.py
 *
 * Notes on Decimal serialisation:
 *   asyncpg returns NUMERIC columns as Python Decimal.
 *   FastAPI serialises Decimal as a JSON number.
 *   However, to preserve precision we treat prices/amounts as strings in
 *   the frontend (same pattern as Session.price in the agenda module).
 */

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

export type SessionStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'

// ---------------------------------------------------------------------------
// Mirrors PeriodSummaryResponse (GET /reports/summary)
// ---------------------------------------------------------------------------

export interface PeriodSummary {
  period_start: string   // YYYY-MM-DD
  period_end: string     // YYYY-MM-DD
  total_sessions: number
  total_amount: string   // Decimal serialised as string e.g. "1500.00"
  status_filter: string[]
}

// ---------------------------------------------------------------------------
// Mirrors SessionEntry (nested inside ClientBillingEntry)
// ---------------------------------------------------------------------------

export interface SessionEntry {
  session_id: string
  client_id: string
  client_name: string
  scheduled_at: string   // ISO 8601
  duration_minutes: number
  price: string          // Decimal serialised as string
  status: string
  notes: string | null
}

// ---------------------------------------------------------------------------
// Mirrors ClientBillingEntry (nested inside BillingReportResponse)
// ---------------------------------------------------------------------------

export interface ClientBillingEntry {
  client_id: string
  client_name: string
  session_count: number
  total_amount: string   // Decimal serialised as string
  sessions: SessionEntry[]
}

// ---------------------------------------------------------------------------
// Mirrors BillingReportResponse (GET /reports/billing)
// ---------------------------------------------------------------------------

export interface BillingReport {
  period_start: string
  period_end: string
  total_sessions: number
  total_amount: string
  clients: ClientBillingEntry[]
  ai_insights: string | null
  generated_at: string   // ISO 8601
}

// ---------------------------------------------------------------------------
// Query params shared by both endpoints
// ---------------------------------------------------------------------------

export interface ReportParams {
  start_date: string     // YYYY-MM-DD
  end_date: string       // YYYY-MM-DD
  status_filter: string[]
  client_id?: string
}

// ---------------------------------------------------------------------------
// Status picker options — used by PeriodFilter
// ---------------------------------------------------------------------------

export const STATUS_OPTIONS: { value: SessionStatus; label: string }[] = [
  { value: 'completed', label: 'Realizadas'  },
  { value: 'scheduled', label: 'Agendadas'   },
  { value: 'cancelled', label: 'Canceladas'  },
  { value: 'no_show',   label: 'Faltou'      },
]
