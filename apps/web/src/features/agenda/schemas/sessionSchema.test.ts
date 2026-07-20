/**
 * Unit tests for sessionSchema (Zod validation).
 * Pure synchronous — no mocks, no providers needed.
 */

import { sessionSchema } from './sessionSchema'

// ---------------------------------------------------------------------------
// Shared valid base payload
// ---------------------------------------------------------------------------

const validPayload = {
  client_id: 'some-uuid-1234-5678',
  scheduled_at: '2025-07-21T10:00',
  duration_minutes: 50,
  price: '150.00',
  status: 'scheduled' as const,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('sessionSchema', () => {
  it('aceita payload mínimo válido', () => {
    const result = sessionSchema.safeParse(validPayload)
    expect(result.success).toBe(true)
  })

  it('aceita payload completo com notes', () => {
    const result = sessionSchema.safeParse({
      ...validPayload,
      notes: 'Observações sobre a sessão',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.notes).toBe('Observações sobre a sessão')
    }
  })

  it('rejeita client_id vazio', () => {
    const result = sessionSchema.safeParse({ ...validPayload, client_id: '' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path[0])
      expect(paths).toContain('client_id')
    }
  })

  it('rejeita scheduled_at vazio', () => {
    const result = sessionSchema.safeParse({
      ...validPayload,
      scheduled_at: '',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path[0])
      expect(paths).toContain('scheduled_at')
    }
  })

  it('z.coerce.number() aceita string "50" como duration_minutes', () => {
    // HTML number inputs submit string values — z.coerce.number() handles this.
    const result = sessionSchema.safeParse({
      ...validPayload,
      duration_minutes: '50',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.duration_minutes).toBe(50)
    }
  })

  it('rejeita duration_minutes menor que 15', () => {
    const result = sessionSchema.safeParse({
      ...validPayload,
      duration_minutes: 10,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path[0])
      expect(paths).toContain('duration_minutes')
    }
  })

  it('rejeita duration_minutes maior que 480', () => {
    const result = sessionSchema.safeParse({
      ...validPayload,
      duration_minutes: 500,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path[0])
      expect(paths).toContain('duration_minutes')
    }
  })

  it('rejeita price com formato inválido', () => {
    const result = sessionSchema.safeParse({ ...validPayload, price: 'abc' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path[0])
      expect(paths).toContain('price')
    }
  })

  it('aceita price com vírgula decimal "150,00"', () => {
    // Backend stores Decimal as string; Brazilian locale uses comma as separator.
    const result = sessionSchema.safeParse({
      ...validPayload,
      price: '150,00',
    })
    expect(result.success).toBe(true)
  })

  it('rejeita status com valor inválido', () => {
    const result = sessionSchema.safeParse({
      ...validPayload,
      status: 'invalid_status',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path[0])
      expect(paths).toContain('status')
    }
  })
})
