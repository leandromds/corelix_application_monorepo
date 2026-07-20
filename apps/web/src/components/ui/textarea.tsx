import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => {
  return (
    <textarea
      ref={ref}
      className={cn(
        'w-full px-3 py-2 text-[13px] min-h-[80px] resize-y',
        'bg-white text-[var(--text-primary)] border border-[var(--border-default)]',
        'rounded-[var(--radius-md)] outline-none transition-colors',
        'placeholder:text-[var(--text-muted)]',
        'focus:border-[var(--text-primary)]',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        '[data-theme=dark]:bg-[var(--bg-surface)]',
        className
      )}
      {...props}
    />
  )
})
Textarea.displayName = 'Textarea'

export { Textarea }
