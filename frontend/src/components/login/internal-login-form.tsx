"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function InternalLoginForm({ csrf }: { csrf: string }) {
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  return <form action="/auth/login" method="post" className="space-y-5" onSubmit={() => setSubmitting(true)}>
    <input type="hidden" name="csrf" value={csrf} />
    <div className="space-y-2">
      <Label htmlFor="email">E-mail</Label>
      <Input id="email" name="email" type="email" autoComplete="username" inputMode="email"
        required autoFocus aria-describedby="email-help" />
      <p id="email-help" className="text-xs text-muted-foreground">Use o e-mail cadastrado pelo administrador.</p>
    </div>
    <div className="space-y-2">
      <Label htmlFor="password">Senha</Label>
      <div className="relative">
        <Input id="password" name="password" type={visible ? "text" : "password"}
          autoComplete="current-password" required className="pr-12" />
        <button type="button" onClick={() => setVisible(value => !value)}
          aria-label={visible ? "Ocultar senha" : "Mostrar senha"}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {visible ? <EyeOff className="size-4" aria-hidden="true" /> : <Eye className="size-4" aria-hidden="true" />}
        </button>
      </div>
    </div>
    <Button type="submit" className="w-full" disabled={submitting} aria-disabled={submitting}>
      {submitting ? "Entrando…" : "Entrar"}
    </Button>
  </form>;
}
