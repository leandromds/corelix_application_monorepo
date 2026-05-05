import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'
import type { BillingReport, ReportParams } from '../types'
import { serializeReportParams } from './useReportSummary'

/**
 * Fetches the full billing report for a given period.
 *
 * Design: intentionally disabled on mount (params=null) so the expensive
 * AI call only fires when the user explicitly clicks "Gerar Relatório".
 * Passing non-null params to this hook is the trigger — TanStack Query
 * refetches automatically whenever params changes (new queryKey), so
 * subsequent clicks with different dates work without manual invalidation.
 *
 * @param params  null → query disabled; non-null → query fires immediately.
 */
export function useBillingReport(params: ReportParams | null) {
  return useQuery({
    queryKey: ['reports', 'billing', params],
    queryFn: async () => {
      const p = params! // safe: enabled:false prevents call when params=null
      const { data } = await api.get<BillingReport>('/reports/billing', {
        params: {
          start_date: p.start_date,
          end_date: p.end_date,
          status_filter: p.status_filter,
          ...(p.client_id != null ? { client_id: p.client_id } : {}),
        },
        paramsSerializer: serializeReportParams,
      })
      return data
    },
    enabled: params !== null,
  })
}
