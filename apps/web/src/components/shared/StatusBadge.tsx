/**
 * StatusBadge — maps session and client statuses to compact styled badges.
 *
 * Uses .badge + .badge-{variant} CSS classes from index.css.
 * No inline styles — all colors are owned by the CSS design system.
 */

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SessionStatus = "scheduled" | "completed" | "cancelled" | "no_show";
type ClientStatus = "active" | "inactive";
export type Status = SessionStatus | ClientStatus;

interface BadgeConfig {
  /** Portuguese display label */
  label: string;
  /** CSS modifier class, e.g. "badge-confirmed" */
  badgeClass: string;
}

// ---------------------------------------------------------------------------
// Status → badge config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<Status, BadgeConfig> = {
  // Session statuses
  scheduled: { label: "Agendada", badgeClass: "badge-confirmed" },
  completed: { label: "Realizada", badgeClass: "badge-confirmed" },
  cancelled: { label: "Cancelada", badgeClass: "badge-cancelled" },
  no_show: { label: "Faltou", badgeClass: "badge-noshow" },

  // Client statuses
  active: { label: "Ativo", badgeClass: "badge-confirmed" },
  inactive: { label: "Inativo", badgeClass: "badge-noshow" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { label, badgeClass } = STATUS_CONFIG[status];

  return <span className={cn("badge", badgeClass, className)}>{label}</span>;
}
