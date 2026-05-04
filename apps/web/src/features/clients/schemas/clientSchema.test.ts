import { clientSchema } from '@/features/clients/schemas/clientSchema'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const validBase = {
  full_name: 'Ana Lima',
  phone: '+5511999999999',
  whatsapp_opt_in: false,
  email_opt_in: false,
} as const

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('clientSchema', () => {
  it('aceita payload mínimo válido (full_name + phone + opt-ins)', () => {
    const result = clientSchema.safeParse(validBase)
    expect(result.success).toBe(true)
  })

  it('aceita payload completo com email e notes', () => {
    const result = clientSchema.safeParse({
      ...validBase,
      email: 'ana@example.com',
      notes: 'Paciente preferencial',
    })
    expect(result.success).toBe(true)
  })

  it('aceita email como string vazia (campo optional)', () => {
    const result = clientSchema.safeParse({
      ...validBase,
      email: '',
    })
    expect(result.success).toBe(true)
  })

  it('rejeita full_name com menos de 2 caracteres', () => {
    const result = clientSchema.safeParse({ ...validBase, full_name: 'A' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const nameError = result.error.issues.find((i) => i.path[0] === 'full_name')
      expect(nameError?.message).toBe('Nome deve ter pelo menos 2 caracteres')
    }
  })

  it('rejeita telefone sem o prefixo +55', () => {
    const result = clientSchema.safeParse({ ...validBase, phone: '11999999999' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const phoneError = result.error.issues.find((i) => i.path[0] === 'phone')
      expect(phoneError?.message).toBe('Formato: +5511999999999')
    }
  })

  it('rejeita telefone com espaços no meio (formato errado)', () => {
    // "+55 11 99999" — tem espaços, não casa com /^\+55\d{10,11}$/
    const result = clientSchema.safeParse({ ...validBase, phone: '+55 11 99999' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const phoneError = result.error.issues.find((i) => i.path[0] === 'phone')
      expect(phoneError?.message).toBe('Formato: +5511999999999')
    }
  })

  it('rejeita email malformado quando presente', () => {
    const result = clientSchema.safeParse({ ...validBase, email: 'nao-eh-email' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const emailError = result.error.issues.find((i) => i.path[0] === 'email')
      expect(emailError?.message).toBe('E-mail inválido')
    }
  })

  it('rejeita quando whatsapp_opt_in está ausente (campo obrigatório boolean)', () => {
    const { whatsapp_opt_in: _, ...withoutOptIn } = validBase
    const result = clientSchema.safeParse(withoutOptIn)
    expect(result.success).toBe(false)
    if (!result.success) {
      const optInError = result.error.issues.find((i) => i.path[0] === 'whatsapp_opt_in')
      expect(optInError).toBeDefined()
    }
  })
})
