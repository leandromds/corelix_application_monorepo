import {
  startOfWeek,
  addDays,
  format,
  isSameDay,
  parseISO,
  isToday,
} from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { cn } from '@/lib/utils'
import type { Session, SessionStatus } from '../types'
import { STATUS_LABELS } from '../types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SLOT_HEIGHT = 48 // px per 30-min slot
const START_HOUR = 8
const END_HOUR = 19
const TOTAL_SLOTS = (END_HOUR - START_HOUR) * 2 // 22 slots (08:00–18:30)
const TOTAL_HEIGHT = TOTAL_SLOTS * SLOT_HEIGHT // 1056 px

// ---------------------------------------------------------------------------
// Status colour map
// ---------------------------------------------------------------------------

type StatusColor = { bg: string; border: string; text: string }

const STATUS_COLORS: Record<SessionStatus, StatusColor> = {
  scheduled: {
    bg: 'rgba(79, 70, 229, 0.12)',
    border: '#4f46e5',
    text: '#4f46e5',
  },
  completed: {
    bg: 'rgba(5, 150, 105, 0.10)',
    border: '#059669',
    text: '#059669',
  },
  cancelled: {
    bg: 'rgba(220, 38, 38, 0.10)',
    border: 'var(--danger)',
    text: 'var(--danger)',
  },
  no_show: {
    bg: 'rgba(107, 114, 128, 0.10)',
    border: 'var(--text-muted)',
    text: 'var(--text-muted)',
  },
}

// ---------------------------------------------------------------------------
// Avatar colour helper (deterministic hash)
// ---------------------------------------------------------------------------

const AVATAR_COLORS = [
  '#4f46e5',
  '#0891b2',
  '#059669',
  '#dc2626',
  '#7c3aed',
  '#d97706',
  '#0f766e',
]

function getAvatarColor(name: string): string {
  let hash = 0
  for (const c of name) hash = (hash << 5) - hash + c.charCodeAt(0)
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]!
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

function getWeekDays(ref: Date): Date[] {
  const mon = startOfWeek(ref, { weekStartsOn: 1 })
  return Array.from({ length: 5 }, (_, i) => addDays(mon, i))
}

function getSessionsForDay(sessions: Session[], day: Date): Session[] {
  return sessions.filter((s) => isSameDay(parseISO(s.scheduled_at), day))
}

/** Returns the top pixel offset for a session inside a day column, or -1 if out of range. */
function getSessionTop(scheduledAt: string): number {
  const date = parseISO(scheduledAt)
  const hour = date.getHours()
  const minute = date.getMinutes()
  if (hour < START_HOUR || hour >= END_HOUR) return -1
  const slot = (hour - START_HOUR) * 2 + Math.floor(minute / 30)
  return slot * SLOT_HEIGHT
}

/** Returns the pixel height of a session block (minimum half a slot). */
function getSessionHeight(durationMinutes: number): number {
  return Math.max(Math.ceil(durationMinutes / 30) * SLOT_HEIGHT, SLOT_HEIGHT / 2)
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface WeekViewProps {
  sessions: Session[]
  /** Any day inside the target week — Monday will be derived automatically. */
  currentWeek: Date
  onSessionClick: (session: Session) => void
  onNewSession: (date: Date) => void
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WeekView({
  sessions,
  currentWeek,
  onSessionClick,
  onNewSession,
}: WeekViewProps) {
  const weekDays = getWeekDays(currentWeek)

  // Time labels for the left column — only show the whole-hour labels.
  const timeLabels: string[] = Array.from({ length: TOTAL_SLOTS }, (_, i) => {
    const hour = START_HOUR + Math.floor(i / 2)
    const minute = i % 2 === 0 ? '00' : '30'
    return `${hour}:${minute}`
  })

  function handleColumnClick(
    day: Date,
    e: React.MouseEvent<HTMLDivElement>,
  ): void {
    // Ignore clicks that originated on a session block (stopPropagation handles those).
    const rect = e.currentTarget.getBoundingClientRect()
    const y = e.clientY - rect.top
    const slot = Math.max(0, Math.min(TOTAL_SLOTS - 1, Math.floor(y / SLOT_HEIGHT)))
    const hour = START_HOUR + Math.floor(slot / 2)
    const minute = slot % 2 === 0 ? 0 : 30
    const date = new Date(day)
    date.setHours(hour, minute, 0, 0)
    onNewSession(date)
  }

  const gridCols: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '60px repeat(5, 1fr)',
  }

  return (
    <div
      className="overflow-auto rounded-xl"
      style={{ background: 'var(--bg-surface-card)' }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Header row — sticky so it stays visible while scrolling             */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="sticky top-0 z-10"
        style={{
          ...gridCols,
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-surface-card)',
        }}
      >
        {/* Corner */}
        <div
          className="p-3"
          style={{ borderRight: '1px solid var(--border-default)' }}
        />

        {weekDays.map((day) => {
          const today = isToday(day)
          return (
            <div
              key={day.toISOString()}
              className={cn('p-3 text-center', today && 'border-b-2')}
              style={{
                borderLeft: '1px solid var(--border-default)',
                borderBottomColor: today ? 'var(--color-primary)' : undefined,
              }}
            >
              <div
                className="text-xs font-medium uppercase tracking-wide"
                style={{
                  color: today ? 'var(--color-primary)' : 'var(--text-muted)',
                }}
              >
                {format(day, 'EEE', { locale: ptBR })}
              </div>
              <div
                className="text-lg font-bold mt-0.5"
                style={{
                  color: today ? 'var(--color-primary)' : 'var(--text-primary)',
                  fontFamily: 'var(--font-heading)',
                }}
              >
                {format(day, 'd')}
              </div>
            </div>
          )
        })}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Body — time labels + day columns                                   */}
      {/* ------------------------------------------------------------------ */}
      <div style={gridCols}>
        {/* Time column */}
        <div style={{ borderRight: '1px solid var(--border-default)' }}>
          {timeLabels.map((label, i) => (
            <div
              key={i}
              className="flex items-start justify-end pr-2 pt-1"
              style={{
                height: SLOT_HEIGHT,
                borderBottom: '1px solid var(--border-default)',
                opacity: i % 2 === 0 ? 1 : 0.4,
              }}
            >
              {i % 2 === 0 && (
                <span
                  className="text-xs leading-none"
                  style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}
                >
                  {label}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {weekDays.map((day, dayIndex) => (
          <div
            key={dayIndex}
            style={{
              position: 'relative',
              height: TOTAL_HEIGHT,
              borderLeft: '1px solid var(--border-default)',
              cursor: 'crosshair',
            }}
            onClick={(e) => handleColumnClick(day, e)}
          >
            {/* Subtle today highlight */}
            {isToday(day) && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'rgba(79, 70, 229, 0.025)',
                  pointerEvents: 'none',
                }}
              />
            )}

            {/* Horizontal grid lines */}
            {timeLabels.map((_, i) => (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  top: i * SLOT_HEIGHT,
                  left: 0,
                  right: 0,
                  height: SLOT_HEIGHT,
                  borderBottom: '1px solid var(--border-default)',
                  opacity: i % 2 === 0 ? 0.6 : 0.2,
                  pointerEvents: 'none',
                }}
              />
            ))}

            {/* Session blocks */}
            {getSessionsForDay(sessions, day).map((session) => {
              const top = getSessionTop(session.scheduled_at)
              if (top < 0) return null

              const height = getSessionHeight(session.duration_minutes)
              const colors = STATUS_COLORS[session.status]
              const name = session.client_name ?? 'Cliente'
              const nameColor = getAvatarColor(name)

              return (
                <div
                  key={session.id}
                  style={{
                    position: 'absolute',
                    top: top + 1,
                    height: height - 2,
                    left: 3,
                    right: 3,
                    background: colors.bg,
                    borderLeft: `3px solid ${colors.border}`,
                    borderRadius: 'var(--radius-sm, 4px)',
                    overflow: 'hidden',
                    padding: '2px 5px',
                    cursor: 'pointer',
                    zIndex: 1,
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSessionClick(session)
                  }}
                  title={`${name} — ${session.duration_minutes} min — ${STATUS_LABELS[session.status]}`}
                >
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: nameColor,
                      lineHeight: 1.3,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {name}
                  </div>
                  {height >= SLOT_HEIGHT && (
                    <div
                      style={{
                        fontSize: 9,
                        color: colors.text,
                        opacity: 0.85,
                        lineHeight: 1.3,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {session.duration_minutes}min · {STATUS_LABELS[session.status]}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
