import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2 text-sm text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] transition-all outline-none",
        "focus-visible:border-[var(--to-accent-amber)] focus-visible:shadow-[var(--glow-amber)]/40",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        "aria-invalid:border-[var(--to-error)] aria-invalid:shadow-[var(--glow-red)]/30",
        className
      )}
      {...props}
    />
  )
}

export { Input }
