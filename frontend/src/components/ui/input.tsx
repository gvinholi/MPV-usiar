import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return <input type={type} data-slot="input" className={cn(
    "h-10 w-full rounded-md border bg-background px-3 py-2 text-sm shadow-xs outline-none transition-colors",
    "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50",
    className,
  )} {...props} />;
}
