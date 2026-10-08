"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { usePathname, useRouter } from "next/navigation";
import { CalendarDays, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function localInputValue(iso?: string) {
  if (!iso) return "";
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 19);
}

function asIso(value: string) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

export function PeriodFilter({ initialFrom, initialTo }: { initialFrom?: string; initialTo?: string }) {
  const fromRef = useRef<HTMLInputElement>(null);
  const toRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  const [pending, startTransition] = useTransition();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (initialFrom && fromRef.current) fromRef.current.value = localInputValue(initialFrom);
    if (initialTo && toRef.current) toRef.current.value = localInputValue(initialTo);
  }, [initialFrom, initialTo]);

  function apply(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const currentFrom = String(fields.get("from_datetime") ?? "");
    const currentTo = String(fields.get("to_datetime") ?? "");
    const start = asIso(currentFrom); const end = asIso(currentTo);
    if ((currentFrom && !start) || (currentTo && !end)) { setMessage("Informe datas e horários válidos."); return; }
    if (start && end && Date.parse(start) >= Date.parse(end)) {
      setMessage("O início deve ser anterior ao fim."); return;
    }
    setMessage("");
    const query = new URLSearchParams();
    if (start) query.set("from_datetime", start);
    if (end) query.set("to_datetime", end);
    startTransition(() => router.push(query.size ? `${pathname}?${query}` : pathname));
  }

  function clear() {
    if (fromRef.current) fromRef.current.value = "";
    if (toRef.current) toRef.current.value = "";
    setMessage("");
    startTransition(() => router.push(pathname));
  }

  return <Card aria-labelledby="period-filter-title">
    <CardHeader>
      <div className="flex items-center gap-2"><CalendarDays className="size-5 text-primary" aria-hidden="true" /><CardTitle id="period-filter-title">Período</CardTitle></div>
      <CardDescription>Os limites são opcionais. A consulta inclui o início e exclui o instante final.</CardDescription>
    </CardHeader>
    <CardContent>
      <form onSubmit={apply} className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
        <div className="space-y-2"><Label htmlFor="from-datetime">Início</Label><Input ref={fromRef} id="from-datetime" name="from_datetime" type="datetime-local" step="1" disabled={pending} /></div>
        <div className="space-y-2"><Label htmlFor="to-datetime">Fim exclusivo</Label><Input ref={toRef} id="to-datetime" name="to_datetime" type="datetime-local" step="1" disabled={pending} /></div>
        <div className="flex gap-2"><Button type="submit" disabled={pending}>{pending ? "Aplicando…" : "Aplicar"}</Button><Button type="button" variant="outline" onClick={clear} disabled={pending}><RotateCcw className="size-4" aria-hidden="true" />Limpar</Button></div>
      </form>
      <p className="mt-3 min-h-5 text-sm text-red-700" role="alert" aria-live="polite">{message}</p>
    </CardContent>
  </Card>;
}
