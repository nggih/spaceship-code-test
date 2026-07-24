import * as React from "react";
import { cn } from "../../lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[#b9f55b]/20 bg-[#b9f55b]/8 px-2.5 py-1 text-xs font-medium text-[#d8ff9e]",
        className,
      )}
      {...props}
    />
  );
}
