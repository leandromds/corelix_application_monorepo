import { forwardRef } from 'react'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

const Checkbox = forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      'peer w-4 h-4 shrink-0 rounded-[var(--radius-sm)] border border-[var(--border-default)]',
      'bg-white transition-colors outline-none cursor-pointer',
      'focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-1',
      'disabled:cursor-not-allowed disabled:opacity-50',
      'data-[state=checked]:bg-[var(--color-primary)] data-[state=checked]:border-[var(--color-primary)] data-[state=checked]:text-[var(--color-primary-fg)]',
      '[data-theme=dark]:bg-[var(--bg-surface)]',
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center text-current">
      <Check className="w-3 h-3 text-white" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
Checkbox.displayName = CheckboxPrimitive.Root.displayName

export { Checkbox }
