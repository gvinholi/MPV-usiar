"use client";
import * as React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;
export const SheetTitle = Dialog.Title;
export const SheetDescription = Dialog.Description;
export function SheetContent({ className, children, ...props }: React.ComponentProps<typeof Dialog.Content>) {
  return <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/50" />
    <Dialog.Content className={cn("fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r bg-background p-6 shadow-xl", className)} {...props}>
      {children}
      <Dialog.Close className="absolute right-4 top-5 rounded-md p-1 focus-visible:outline-2 focus-visible:outline-ring"><X className="size-5" /><span className="sr-only">Fechar menu</span></Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>;
}
