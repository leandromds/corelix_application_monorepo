/**
 * Avatar — circular component that displays user initials.
 *
 * Also exports `getInitials`, a pure helper that derives
 * two-character initials from a full name string.
 */

import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AvatarProps {
  /** Pre-computed initials to display (use getInitials to generate). */
  initials: string
  /** Override background color. Defaults to var(--color-primary). */
  color?: string
  size?: 'sm' | 'md' | 'default' | 'lg'
  className?: string
}

interface SizeConfig {
  px: number
  fontSize: string
}

// ---------------------------------------------------------------------------
// Size map — pixel dimensions and matching font size per size variant
// ---------------------------------------------------------------------------

const SIZE_MAP: Record<NonNullable<AvatarProps['size']>, SizeConfig> = {
  sm:      { px: 28, fontSize: '10px' },
  default: { px: 32, fontSize: '11px' },
  md:      { px: 36, fontSize: '12px' },
  lg:      { px: 40, fontSize: '13px' },
}

// ---------------------------------------------------------------------------
// Helper — derive initials from a full name
// ---------------------------------------------------------------------------

/**
 * Returns up to two uppercase characters from the first two words of `name`.
 *
 * Examples:
 *   "Ana Lima"      → "AL"
 *   "Carlos"        → "C"
 *   "  "            → "?"
 */
export function getInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)

  if (words.length === 0) return '?'

  const first = words[0]![0]!.toUpperCase()
  if (words.length === 1) return first

  const second = words[1]![0]!.toUpperCase()
  return `${first}${second}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Avatar({
  initials,
  color,
  size = 'default',
  className,
}: AvatarProps) {
  const { px, fontSize } = SIZE_MAP[size]

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-full flex-shrink-0 select-none',
        className,
      )}
      style={{
        width: `${px}px`,
        height: `${px}px`,
        background: color ?? 'var(--color-primary)',
        fontSize,
        fontWeight: 700,
        color: 'white',
      }}
      aria-label={initials}
    >
      {initials}
    </div>
  )
}
