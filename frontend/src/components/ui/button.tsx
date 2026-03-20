import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:outline-none",
  {
    variants: {
      variant: {
        default: "bg-[var(--to-accent-amber)] text-[#080b10] hover:shadow-[var(--glow-amber)] focus-visible:shadow-[var(--glow-amber)]/50",
        destructive:
          "bg-[var(--to-error)] text-white hover:bg-[var(--to-error)]/90 focus-visible:shadow-[var(--glow-red)]/50",
        outline:
          "border border-[var(--to-border)] text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] focus-visible:shadow-[var(--glow-amber)]/50",
        secondary:
          "bg-[var(--to-surface-raised)] text-[var(--to-text-primary)] border border-[var(--to-border)] hover:bg-[var(--to-surface-overlay)] focus-visible:shadow-[var(--glow-amber)]/50",
        ghost:
          "text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] focus-visible:shadow-[var(--glow-amber)]/50",
        link: "text-[var(--to-accent-amber)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        xs: "h-6 gap-1 rounded-md px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-6 rounded-md [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
