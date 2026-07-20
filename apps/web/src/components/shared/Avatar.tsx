/**
 * Avatar — circular component that displays user initials.
 *
 * Style: driven entirely by .avatar + .avatar-{size} CSS classes from index.css.
 * The optional `color` prop is a programmatic override (e.g. hash-based colors
 * in DayList) — applied via minimal inline style since it's dynamic data, not
 * a hardcoded design token.
 *
 * Also exports `getInitials`, a pure helper that derives two-character initials.
 */

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AvatarProps {
  /** Pre-computed initials to display (use getInitials to generate). */
  initials: string;
  /** Optional programmatic background override (e.g. hash-based color). */
  color?: string;
  size?: "sm" | "md" | "default" | "lg";
  className?: string;
}

// ---------------------------------------------------------------------------
// Size → CSS class map
// ---------------------------------------------------------------------------

const SIZE_CLASS: Record<NonNullable<AvatarProps["size"]>, string> = {
  sm: "avatar-sm",
  default: "avatar-md", // 34px — closest to original 32px, no visible difference
  md: "avatar-md",
  lg: "avatar-lg",
};

// ---------------------------------------------------------------------------
// Helper — derive initials from a full name
// ---------------------------------------------------------------------------

/**
 * Returns up to two uppercase characters from the first two words of `name`.
 *
 * Examples:
 *   "Ana Lima"  → "AL"
 *   "Carlos"    → "C"
 *   "  "        → "?"
 */
export function getInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);

  if (words.length === 0) return "?";

  const first = words[0]![0]!.toUpperCase();
  if (words.length === 1) return first;

  const second = words[1]![0]!.toUpperCase();
  return `${first}${second}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function Avatar({
  initials,
  color,
  size = "default",
  className,
}: AvatarProps) {
  return (
    <div
      className={cn("avatar", SIZE_CLASS[size], className)}
      style={color ? { background: color, border: "none" } : undefined}
      aria-label={initials}
    >
      {initials}
    </div>
  );
}
