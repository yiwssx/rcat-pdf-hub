import * as React from "react";
import { cn } from "@/lib/utils";

/** Native select preserves browser keyboard, form and mobile picker behavior. */
const NativeSelect = React.forwardRef<HTMLSelectElement, React.ComponentProps<"select">>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "flex min-h-11 w-full min-w-0 rounded-md border border-input bg-white px-3 py-2 text-base text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
NativeSelect.displayName = "NativeSelect";
export { NativeSelect };
