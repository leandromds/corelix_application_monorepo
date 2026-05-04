/**
 * StatusBadge — maps session and client statuses to compact styled badges.
 *
 * All colors are resolved at runtime via CSS variables defined in index.css,
 * which means the badge automatically adapts to light / dark themes.
 */

import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SessionStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'
type ClientStatus  = 'active'    | 'inactive'
export type Status = SessionStatus | ClientStatus

interface BadgeConfig {
  /** Portuguese display label */
  label: string
  /** CSS variable name (without `var()`) for background */
  bgVar: string
  /** CSS variable name (without `var()`) for text and border */
  fgVar: string
}

// ---------------------------------------------------------------------------
// Status → badge config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<Status, BadgeConfig> = {
  // Session statuses
  scheduled: {
    label: 'Agendada',
    bgVar: '--badge-confirmed-bg',
    fgVar: '--badge-confirmed-fg',
  },
  completed: {
    label: 'Realizada',
    bgVar: '--badge-confirmed-bg',
    fgVar: '--badge-confirmed-fg',
  },
  cancelled: {
    label: 'Cancelada',
    bgVar: '--badge-cancelled-bg',
    fgVar: '--badge-cancelled-fg',
  },
  no_show: {
    label: 'Faltou',
    bgVar: '--badge-noshow-bg',
    fgVar: '--badge-noshow-fg',
  },

  // Client statuses
  active: {
    label: 'Ativo',
    bgVar: '--badge-confirmed-bg',
    fgVar: '--badge-confirmed-fg',
  },
  inactive: {
    label: 'Inativo',
    bgVar: '--badge-noshow-bg',
    fgVar: '--badge-noshow-fg',
  },
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface StatusBadgeProps {
  status: Status
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { label, bgVar, fgVar } = STATUS_CONFIG[status]

  return (
    <span
      className={cn(
        'inline-flex items-center text-[10px] font-bold',
        'px-[9px] py-[2px] rounded-full border',
        className,
      )}
      style={{
        background:   `var(${bgVar})`,
        color:        `var(${fgVar})`,
        borderColor:  `var(${fgVar})`,
      }}
    >
      {label}
    </span>
  )
}
