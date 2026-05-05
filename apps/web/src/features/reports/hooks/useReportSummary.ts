import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { PeriodSummary, ReportParams } from '../types'

/**
 * Fetches the lightweight period summary (total sessions + total amount).
 *
 * Used for dashboard-style KPI cards that update live as the user adjusts
 * the filter. Does NOT trigger an AI call — fast by design.
 *
 * Serialisation note:
 *   Axios default bracket-notation breaks FastAPI `list[str]` query params:
 *     axios default → status_filter[]=completed   (FastAPI rejects)
 *     we want       → status_filter=completed     (FastAPI accepts)
 *   Fix: pass a custom paramsSerializer function that uses URLSearchParams
 *   to build the query string with repeated keys for array values.
 */
export function useReportSummary(params: ReportParams, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'summary', params],
    queryFn: async () => {
      const { data } = await api.get<PeriodSummary>('/reports/summary', {
        params: {
          start_date: params.start_date,
          end_date: params.end_date,
          status_filter: params.status_filter,
        },
        paramsSerializer: serializeReportParams,
      })
      return data
    },
    enabled,
  })
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Serialises params to the FastAPI-compatible format:
 *   { status_filter: ['completed', 'no_show'] }
 *   → "status_filter=completed&status_filter=no_show"
 *
 * Axios's built-in serialiser produces "status_filter[]=…" which FastAPI
 * cannot parse for `list[str]` query parameters.
 */
export function serializeReportParams(
  params: Record<string, unknown>,
): string {
  const sp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      for (const v of value as string[]) {
        sp.append(key, v)
      }
    } else if (value != null) {
      sp.append(key, String(value))
    }
  }
  return sp.toString()
}
