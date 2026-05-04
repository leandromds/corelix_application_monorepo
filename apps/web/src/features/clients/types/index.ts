export interface Client {
  id: string             // UUID
  full_name: string
  phone: string
  email: string | null
  notes: string | null
  is_active: boolean
  whatsapp_opt_in: boolean
  email_opt_in: boolean
  created_at: string     // ISO 8601
  updated_at: string
}

export interface ClientsListParams {
  search?: string
  is_active?: boolean
  skip?: number
  limit?: number
}

export type CreateClientPayload = {
  full_name: string
  phone: string
  email?: string
  notes?: string
  whatsapp_opt_in: boolean
  email_opt_in: boolean
}

export type UpdateClientPayload = Partial<CreateClientPayload> & {
  is_active?: boolean
}
