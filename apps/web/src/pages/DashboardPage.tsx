import { useAuth } from '@/hooks/useAuth'

export function DashboardPage() {
  const { professional, logout } = useAuth()

  async function handleLogout(): Promise<void> {
    await logout()
    // After logout, professional becomes null → ProtectedRoute redirects to /login
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <header style={styles.header}>
          <div>
            <h1 style={styles.greeting}>
              Olá, {professional?.full_name ?? '—'} 👋
            </h1>
            {professional?.specialty && (
              <p style={styles.specialty}>{professional.specialty}</p>
            )}
          </div>
          <button
            onClick={() => { void handleLogout() }}
            style={styles.logoutBtn}
          >
            Sair
          </button>
        </header>

        <main style={styles.main}>
          <p style={styles.placeholder}>
            Dashboard em construção. Próximos passos: módulo clients e agenda.
          </p>
        </main>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    backgroundColor: '#f9fafb',
  },
  container: {
    maxWidth: 960,
    margin: '0 auto',
    padding: '2rem 1rem',
  },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: '2rem',
  },
  greeting: {
    margin: '0 0 0.25rem',
    fontSize: '1.5rem',
    fontWeight: 700,
    color: '#111827',
  },
  specialty: {
    margin: 0,
    fontSize: '0.875rem',
    color: '#6b7280',
  },
  logoutBtn: {
    padding: '0.5rem 1rem',
    backgroundColor: 'transparent',
    color: '#6b7280',
    border: '1px solid #d1d5db',
    borderRadius: 8,
    fontSize: '0.875rem',
    cursor: 'pointer',
  },
  main: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
    padding: '2rem',
  },
  placeholder: {
    margin: 0,
    color: '#9ca3af',
    fontSize: '0.875rem',
  },
}
