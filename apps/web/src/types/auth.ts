/**
 * Types mirroring the backend Pydantic schemas.
 *
 * Decimal fields (session_price) come as strings from JSON.
 * Dates (created_at) come as ISO 8601 strings.
 */

export interface ProfessionalResponse {
  id: string
  email: string
  full_name: string
  specialty: string | null
  bio: string | null
  phone: string | null
  session_duration: number
  session_price: string | null
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  specialty?: string
  bio?: string
}

export interface AccessTokenResponse {
  access_token: string
  token_type: string
}
