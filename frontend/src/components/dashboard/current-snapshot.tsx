import type { CurrentSnapshotResponse } from "@/lib/server/api/contracts.generated";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CompactMetric, MetricCard } from "./metric-card";

export function PrimaryIndicators({ data }: { data: CurrentSnapshotResponse }) {
  return <section aria-labelledby="primary-indicators-title" className="space-y-4">
    <div><h2 id="primary-indicators-title" className="text-xl font-semibold">Indicadores principais</h2><p className="mt-1 text-sm text-muted-foreground">Contagens atuais da coorte de processos selecionada pelo período.</p></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Processos na coorte" value={data.processes_total} description="Processos cujo primeiro registro pertence ao período." emphasis />
      <MetricCard label="Candidatos atuais" value={data.current_candidate} description="Estado operacional vigente dentro da coorte." />
      <MetricCard label="Precisam de revisão" value={data.needs_review} description="Itens atualmente na fila de revisão humana." />
      <MetricCard label="Selecionados" value={data.selected} description="Decisões humanas vigentes de seleção." />
    </div>
  </section>;
}

export function CurrentSnapshot({ data }: { data: CurrentSnapshotResponse }) {
  return <section aria-labelledby="snapshot-title" className="space-y-4">
    <div><h2 id="snapshot-title" className="text-xl font-semibold">Situação atual da coorte</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">Os estados abaixo são os vigentes para os processos selecionados pelo período de primeira observação.</p></div>
    <div className="grid gap-4 xl:grid-cols-3">
      <Card><CardHeader><CardTitle>Estado operacional</CardTitle><CardDescription>Classificação operacional vigente específica do perfil.</CardDescription></CardHeader><CardContent><dl className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1"><CompactMetric label="Candidatos" value={data.current_candidate} /><CompactMetric label="Pendentes" value={data.current_pending} /><CompactMetric label="Descartados" value={data.current_discarded} /></dl></CardContent></Card>
      <Card><CardHeader><CardTitle>Revisões humanas</CardTitle><CardDescription>Decisões vigentes e revisões que ficaram desatualizadas.</CardDescription></CardHeader><CardContent><dl className="grid gap-3 sm:grid-cols-2"><CompactMetric label="Selecionados" value={data.selected} /><CompactMetric label="Pendentes" value={data.human_pending} /><CompactMetric label="Descartados" value={data.human_discarded} /><CompactMetric label="Desatualizadas" value={data.stale_reviews} /></dl></CardContent></Card>
      <Card><CardHeader><CardTitle>Documentos</CardTitle><CardDescription>Cobertura documental acumulada para os processos da coorte.</CardDescription></CardHeader><CardContent><dl className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1"><CompactMetric label="Documentos" value={data.documents_total} /><CompactMetric label="Com artefato" value={data.documents_with_artifact} /><CompactMetric label="Com texto" value={data.documents_with_text} /></dl></CardContent></Card>
    </div>
  </section>;
}
