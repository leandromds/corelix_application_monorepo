import { useState } from 'react'
import {
  format,
  addWeeks,
  subWeeks,
  addDays,
  subDays,
  isSameDay,
  parseISO,
} from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { useSessions } from './hooks/useSessions'
import { useUpdateSession } from './hooks/useUpdateSession'
import { WeekView } from './components/WeekView'
import { DayList } from './components/DayList'
import { SessionForm } from './components/SessionForm'
import type { Session, SessionStatus } from './types'
import { STATUS_LABELS } from './types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = 'week' | 'day'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: string): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(Number(value))
}

function formatDateTime(iso: string): string {
  return format(parseISO(iso), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })
}

// ---------------------------------------------------------------------------
// Sub-component: upcoming sessions table
// ---------------------------------------------------------------------------

interface UpcomingTableProps {
  sessions: Session[]
  onEditSession: (session: Session) => void
}

function UpcomingSessionsTable({ sessions, onEditSession }: UpcomingTableProps) {
  const { mutate: updateSession } = useUpdateSession()
  const now = new Date()

  const upcoming = sessions
    .filter((s) => s.status === 'scheduled' && new Date(s.scheduled_at) > now)
    .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))
    .slice(0, 20)

  if (upcoming.length === 0) return null

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: 'var(--bg-surface-card)',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      {/* Header */}
      <div
        className="px-6 py-4"
        style={{ borderBottom: '1px solid var(--border-default)' }}
      >
        <h3
          className="font-semibold text-base"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-heading)',
          }}
        >
          Próximas sessões
        </h3>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-default)' }}>
              {['Data/Hora', 'Cliente', 'Duração', 'Valor', 'Status', ''].map(
                (header) => (
                  <th
                    key={header}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {header}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {upcoming.map((session) => (
              <tr
                key={session.id}
                style={{ borderBottom: '1px solid var(--border-default)' }}
              >
                <td
                  className="px-4 py-3 text-sm"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {formatDateTime(session.scheduled_at)}
                </td>
                <td
                  className="px-4 py-3 text-sm font-medium"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {session.client_name ?? '—'}
                </td>
                <td
                  className="px-4 py-3 text-sm"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {session.duration_minutes} min
                </td>
                <td
                  className="px-4 py-3 text-sm"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {formatCurrency(session.price)}
                </td>
                <td className="px-4 py-3">
                  <Select
                    value={session.status}
                    onValueChange={(value) => {
                      updateSession({
                        id: session.id,
                        payload: { status: value as SessionStatus },
                      })
                    }}
                  >
                    <SelectTrigger className="w-36 h-7 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(STATUS_LABELS) as SessionStatus[]).map(
                        (value) => (
                          <SelectItem
                            key={value}
                            value={value}
                            className="text-xs"
                          >
                            {STATUS_LABELS[value]}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </td>
                <td className="px-4 py-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs"
                    onClick={() => onEditSession(session)}
                  >
                    Editar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function AgendaPage() {
  const [currentWeek, setCurrentWeek] = useState<Date>(new Date())
  const [viewMode, setViewMode] = useState<ViewMode>('week')
  const [formOpen, setFormOpen] = useState(false)
  const [editingSession, setEditingSession] = useState<Session | null>(null)
  const [defaultFormDate, setDefaultFormDate] = useState<Date | undefined>()

  // Fetch the full month so the calendar doesn't need extra requests when
  // the user navigates days inside the same month.
  const monthParam = format(currentWeek, 'yyyy-MM')
  const { data: sessions = [], isLoading } = useSessions({
    date: monthParam,
    limit: 100,
  })

  // For day view: filter the already-loaded sessions for the selected day.
  const sessionsForDay = sessions.filter((s) =>
    isSameDay(parseISO(s.scheduled_at), currentWeek),
  )

  // ------------------------------------------------------------------
  // Navigation
  // ------------------------------------------------------------------

  function navigate(direction: 'prev' | 'next'): void {
    if (viewMode === 'week') {
      setCurrentWeek((prev) =>
        direction === 'prev' ? subWeeks(prev, 1) : addWeeks(prev, 1),
      )
    } else {
      setCurrentWeek((prev) =>
        direction === 'prev' ? subDays(prev, 1) : addDays(prev, 1),
      )
    }
  }

  // ------------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------------

  function handleEditSession(session: Session): void {
    setEditingSession(session)
    setFormOpen(true)
  }

  function handleNewSession(date: Date): void {
    setDefaultFormDate(date)
    setFormOpen(true)
  }

  function handleFormOpenChange(open: boolean): void {
    setFormOpen(open)
    if (!open) {
      setEditingSession(null)
      setDefaultFormDate(undefined)
    }
  }

  // ------------------------------------------------------------------
  // Header date label
  // ------------------------------------------------------------------

  const headerDate =
    viewMode === 'week'
      ? format(currentWeek, 'MMMM yyyy', { locale: ptBR })
      : format(currentWeek, "d 'de' MMMM yyyy", { locale: ptBR })

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div
      className="p-6 space-y-6"
      style={{ background: 'var(--bg-page)', minHeight: '100vh' }}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Page header                                                       */}
      {/* ---------------------------------------------------------------- */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        {/* Title + current period */}
        <div>
          <h2
            className="text-2xl font-bold"
            style={{
              fontFamily: 'var(--font-heading)',
              color: 'var(--text-primary)',
            }}
          >
            Agenda
          </h2>
          <p
            className="mt-0.5 capitalize text-sm"
            style={{
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-body)',
            }}
          >
            {headerDate}
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Week / Day toggle */}
          <div
            className="flex rounded-lg overflow-hidden border"
            style={{ borderColor: 'var(--border-default)' }}
          >
            {(['week', 'day'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium transition-colors',
                  mode === 'day' && 'border-l',
                )}
                style={{
                  borderColor: 'var(--border-default)',
                  background:
                    viewMode === mode ? 'var(--color-primary)' : 'transparent',
                  color:
                    viewMode === mode
                      ? 'var(--color-primary-fg)'
                      : 'var(--text-primary)',
                }}
                onClick={() => setViewMode(mode)}
              >
                {mode === 'week' ? 'Semana' : 'Dia'}
              </button>
            ))}
          </div>

          {/* Navigation */}
          <Button variant="outline" size="sm" onClick={() => navigate('prev')}>
            <ChevronLeft className="h-4 w-4 mr-1" aria-hidden />
            Anterior
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentWeek(new Date())}
          >
            Hoje
          </Button>

          <Button variant="outline" size="sm" onClick={() => navigate('next')}>
            Próximo
            <ChevronRight className="h-4 w-4 ml-1" aria-hidden />
          </Button>

          {/* New session */}
          <Button
            size="sm"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--color-primary-fg)',
            }}
            onClick={() => {
              setEditingSession(null)
              setDefaultFormDate(undefined)
              setFormOpen(true)
            }}
          >
            <Plus className="h-4 w-4 mr-1" aria-hidden />
            Nova Sessão
          </Button>
        </div>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Calendar card                                                     */}
      {/* ---------------------------------------------------------------- */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'var(--bg-surface-card)',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {isLoading ? (
          <div
            className="p-12 text-center text-sm"
            style={{ color: 'var(--text-muted)' }}
          >
            Carregando agenda…
          </div>
        ) : viewMode === 'week' ? (
          <WeekView
            sessions={sessions}
            currentWeek={currentWeek}
            onSessionClick={handleEditSession}
            onNewSession={handleNewSession}
          />
        ) : (
          <DayList
            sessions={sessionsForDay}
            date={currentWeek}
            onSessionClick={handleEditSession}
          />
        )}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Upcoming sessions table                                           */}
      {/* ---------------------------------------------------------------- */}
      <UpcomingSessionsTable
        sessions={sessions}
        onEditSession={handleEditSession}
      />

      {/* ---------------------------------------------------------------- */}
      {/* Create / Edit session modal                                       */}
      {/* ---------------------------------------------------------------- */}
      <SessionForm
        open={formOpen}
        onOpenChange={handleFormOpenChange}
        session={editingSession}
        defaultDate={defaultFormDate}
      />
    </div>
  )
}
