import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { RegisterRequest } from '@/types/auth'

export function RegisterPage() {
  const { register } = useAuth()

  const [formData, setFormData] = useState<RegisterRequest>({
    email: '',
    password: '',
    full_name: '',
    specialty: '',
    bio: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ): void {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    // Strip empty optional fields before sending
    const payload: RegisterRequest = {
      email: formData.email,
      password: formData.password,
      full_name: formData.full_name,
      ...(formData.specialty?.trim() && { specialty: formData.specialty.trim() }),
      ...(formData.bio?.trim() && { bio: formData.bio.trim() }),
    }

    try {
      await register(payload)
      // On success: register() calls login() internally → professional is set
      // → PublicRoute redirects to /dashboard automatically.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar conta')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Criar conta</h1>
        <p style={styles.subtitle}>Secretária Digital</p>

        <form onSubmit={(e) => { void handleSubmit(e) }} noValidate>
          <div style={styles.field}>
            <label htmlFor="email" style={styles.label}>
              E-mail <span style={styles.required}>*</span>
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              required
              autoComplete="email"
              style={styles.input}
              placeholder="seu@email.com"
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="password" style={styles.label}>
              Senha <span style={styles.required}>*</span>
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              required
              minLength={8}
              autoComplete="new-password"
              style={styles.input}
              placeholder="Mínimo 8 caracteres"
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="full_name" style={styles.label}>
              Nome completo <span style={styles.required}>*</span>
            </label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              value={formData.full_name}
              onChange={handleChange}
              required
              autoComplete="name"
              style={styles.input}
              placeholder="Seu nome"
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="specialty" style={styles.label}>
              Especialidade{' '}
              <span style={styles.optional}>(opcional)</span>
            </label>
            <input
              id="specialty"
              name="specialty"
              type="text"
              value={formData.specialty ?? ''}
              onChange={handleChange}
              style={styles.input}
              placeholder="Ex: Fisioterapia, Psicologia..."
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="bio" style={styles.label}>
              Bio <span style={styles.optional}>(opcional)</span>
            </label>
            <textarea
              id="bio"
              name="bio"
              value={formData.bio ?? ''}
              onChange={handleChange}
              rows={3}
              style={{ ...styles.input, resize: 'vertical', fontFamily: 'inherit' }}
              placeholder="Uma breve descrição sobre você..."
            />
          </div>

          {error !== null && (
            <p role="alert" style={styles.error}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              ...styles.button,
              opacity: isSubmitting ? 0.6 : 1,
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
            }}
          >
            {isSubmitting ? 'Criando conta...' : 'Criar conta'}
          </button>
        </form>

        <p style={styles.footer}>
          Já tem conta?{' '}
          <Link to="/login" style={styles.link}>
            Entrar
          </Link>
        </p>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: '#f9fafb',
    padding: '1rem',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    boxShadow: '0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)',
    padding: '2rem',
    width: '100%',
    maxWidth: 440,
  },
  title: {
    margin: '0 0 0.25rem',
    fontSize: '1.5rem',
    fontWeight: 700,
    color: '#111827',
  },
  subtitle: {
    margin: '0 0 1.5rem',
    fontSize: '0.875rem',
    color: '#6b7280',
  },
  field: {
    marginBottom: '1rem',
  },
  label: {
    display: 'block',
    marginBottom: '0.375rem',
    fontSize: '0.875rem',
    fontWeight: 500,
    color: '#374151',
  },
  required: {
    color: '#dc2626',
  },
  optional: {
    color: '#9ca3af',
    fontWeight: 400,
  },
  input: {
    width: '100%',
    boxSizing: 'border-box',
    padding: '0.625rem 0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: '0.875rem',
    color: '#111827',
    outline: 'none',
  },
  error: {
    margin: '0 0 1rem',
    padding: '0.625rem 0.75rem',
    backgroundColor: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: 8,
    fontSize: '0.875rem',
    color: '#dc2626',
  },
  button: {
    width: '100%',
    padding: '0.75rem',
    backgroundColor: '#6366f1',
    color: '#ffffff',
    border: 'none',
    borderRadius: 8,
    fontSize: '0.875rem',
    fontWeight: 600,
    marginBottom: '1rem',
  },
  footer: {
    textAlign: 'center',
    fontSize: '0.875rem',
    color: '#6b7280',
    margin: 0,
  },
  link: {
    color: '#6366f1',
    textDecoration: 'none',
    fontWeight: 500,
  },
}
