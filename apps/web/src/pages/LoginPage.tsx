import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export function LoginPage() {
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await login(email, password)
      // On success: AuthContext sets `professional`, isAuthenticated becomes true,
      // and PublicRoute redirects to /dashboard automatically.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao fazer login')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Entrar</h1>
        <p style={styles.subtitle}>Secretária Digital</p>

        <form onSubmit={(e) => { void handleSubmit(e) }} noValidate>
          <div style={styles.field}>
            <label htmlFor="email" style={styles.label}>
              E-mail
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={styles.input}
              placeholder="seu@email.com"
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="password" style={styles.label}>
              Senha
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              style={styles.input}
              placeholder="Sua senha"
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
            {isSubmitting ? 'Entrando...' : 'Entrar'}
          </button>
        </form>

        <p style={styles.footer}>
          Ainda não tem conta?{' '}
          <Link to="/register" style={styles.link}>
            Criar conta
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
    maxWidth: 400,
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
