import type { DashboardSummaryResponse } from "@/lib/server/api/contracts.generated";

const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "medium", timeStyle: "short", timeZone: "UTC",
});

function periodLabel(period: DashboardSummaryResponse["period"]) {
  const start = period.from_datetime ? dateTime.format(new Date(period.from_datetime)) : undefined;
  const end = period.to_datetime ? dateTime.format(new Date(period.to_datetime)) : undefined;
  if (start && end) return `${start} até antes de ${end}`;
  if (start) return `Desde ${start}`;
  if (end) return `Antes de ${end}`;
  return "Todo o histórico";
}

export function DashboardIntroduction() {
  return <div>
    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-primary">USIAR / Análise</p>
    <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Dashboard operacional</h1>
    <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
      Estado atual da coorte selecionada, atividade do período e cobertura geral da coleta.
    </p>
  </div>;
}

export function DashboardHeader({ profileId, configuredCode, period }: {
  profileId: string;
  configuredCode?: string;
  period: DashboardSummaryResponse["period"];
}) {
  return <header className="space-y-5">
    <DashboardIntroduction />
    <dl className="grid gap-3 rounded-xl border bg-background p-4 text-sm shadow-sm sm:grid-cols-2 sm:p-5">
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Perfil consultado</dt>
        <dd className="mt-1 break-all font-medium">{configuredCode ? `Código ${configuredCode}` : `ID ${profileId}`}</dd>
        {configuredCode && <dd className="mt-1 break-all text-xs text-muted-foreground">ID resolvido: {profileId}</dd>}
      </div>
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Período da consulta</dt>
        <dd className="mt-1 font-medium">{periodLabel(period)}</dd>
        <dd className="mt-1 text-xs text-muted-foreground">Horários exibidos em UTC; o limite final é exclusivo.</dd>
      </div>
    </dl>
  </header>;
}
