import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export type InputProps = InputHTMLAttributes<HTMLInputElement>

const Input = forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      ref={ref}
      className={cn(
        'w-full px-3 py-2 text-[13px]',
        'bg-white text-[var(--text-primary)] border border-[var(--border-default)]',
        'rounded-[var(--radius-md)] outline-none transition-colors',
        'placeholder:text-[var(--text-muted)]',
        'focus:border-[var(--text-primary)] focus:ring-0',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        '[data-theme=dark]:bg-[var(--bg-surface)] [data-theme=dark]:text-[var(--text-primary)]',
        className
      )}
      {...props}
    />
  )
})
Input.displayName = 'Input'

export { Input }
