import * as React from "react";
import { cn } from "../../lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-2xl border border-white/8 bg-[#0d1917]/90 shadow-[0_24px_70px_rgba(0,0,0,.18)]",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";
