import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
import { forwardRef, type ButtonHTMLAttributes } from 'react'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 font-semibold transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed select-none shrink-0',
  {
    variants: {
      variant: {
        default: [
          'bg-[var(--color-primary)] text-[var(--color-primary-fg)]',
          'rounded-[var(--radius-full)]',
          'hover:opacity-80 active:scale-[0.98]',
          'shadow-[var(--shadow-sm)]',
        ].join(' '),
        secondary: [
          'bg-white text-[var(--text-primary)] border border-[var(--border-default)]',
          'rounded-[var(--radius-full)]',
          'hover:bg-[var(--bg-surface-card)]',
          '[data-theme=dark]:bg-[var(--bg-surface)] [data-theme=dark]:text-[var(--text-primary)] [data-theme=dark]:border-[var(--border-default)]',
        ].join(' '),
        destructive: [
          'bg-[var(--danger)] text-white',
          'rounded-[var(--radius-full)]',
          'hover:opacity-90',
        ].join(' '),
        ghost:
          'bg-transparent hover:bg-black/5 rounded-[var(--radius-md)] text-[var(--text-muted)]',
        link: 'bg-transparent text-[var(--info)] p-0 h-auto underline-offset-4 hover:underline',
        outline: [
          'bg-transparent border border-[var(--border-default)] text-[var(--text-primary)]',
          'rounded-[var(--radius-md)]',
          'hover:bg-[var(--bg-surface-card)]',
        ].join(' '),
      },
      size: {
        default: 'px-5 py-2 text-[13px]',
        sm: 'px-3 py-1.5 text-[12px]',
        lg: 'px-6 py-2.5 text-[14px]',
        icon: 'w-8 h-8 p-0 text-[15px]',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
