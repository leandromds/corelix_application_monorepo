import { type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 font-semibold rounded-[var(--radius-full)] transition-colors select-none',
  {
    variants: {
      variant: {
        default:
          'bg-[var(--color-primary)] text-[var(--color-primary-fg)] text-[11px] px-2.5 py-0.5',
        secondary:
          'bg-[var(--bg-surface-card)] text-[var(--text-muted)] text-[11px] px-2.5 py-0.5',
        destructive:
          'bg-[var(--badge-cancelled-bg)] text-[var(--badge-cancelled-fg)] text-[11px] px-2.5 py-0.5',
        outline:
          'border border-[var(--border-default)] text-[var(--text-primary)] text-[11px] px-2.5 py-0.5',
        confirmed:
          'bg-[var(--badge-confirmed-bg)] text-[var(--badge-confirmed-fg)] text-[11px] px-2.5 py-0.5',
        pending:
          'bg-[var(--badge-pending-bg)] text-[var(--badge-pending-fg)] text-[11px] px-2.5 py-0.5',
        cancelled:
          'bg-[var(--badge-cancelled-bg)] text-[var(--badge-cancelled-fg)] text-[11px] px-2.5 py-0.5',
        noshow:
          'bg-[var(--badge-noshow-bg)] text-[var(--badge-noshow-fg)] text-[11px] px-2.5 py-0.5',
        ai: 'bg-[var(--badge-ai-bg)] text-[var(--badge-ai-fg)] text-[11px] px-2.5 py-0.5',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

export interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
