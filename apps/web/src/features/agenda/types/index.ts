export type SessionStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'

export interface Session {
  id: string
  client_id: string
  client_name: string | null // populated in /today and /upcoming
  scheduled_at: string // ISO 8601 with offset
  duration_minutes: number
  price: string // Decimal as string
  status: SessionStatus
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SessionsListParams {
  date?: string // YYYY-MM or YYYY-MM-DD
  status?: SessionStatus
  client_id?: string
  skip?: number
  limit?: number
}

export type CreateSessionPayload = {
  client_id: string
  scheduled_at: string // ISO 8601 with offset
  duration_minutes: number
  price: string
  status: SessionStatus
  notes?: string
}

export type UpdateSessionPayload = Partial<CreateSessionPayload>

export const STATUS_LABELS: Record<SessionStatus, string> = {
  scheduled: 'Agendada',
  completed: 'Realizada',
  cancelled: 'Cancelada',
  no_show: 'Faltou',
}
