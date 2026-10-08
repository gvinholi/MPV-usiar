import type { PeriodActivityResponse } from "@/lib/server/api/contracts.generated";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CompactMetric } from "./metric-card";

export function CollectionActivity({ data }: { data: PeriodActivityResponse }) {
  return <section aria-labelledby="activity-title" className="space-y-4">
    <div><h2 id="activity-title" className="text-xl font-semibold">Atividade no período</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">Eventos ocorridos dentro do intervalo consultado, separados pelo escopo definido pela API.</p></div>
    <div className="grid gap-4 xl:grid-cols-2">
      <Card><CardHeader><CardTitle>Coleta geral</CardTitle><CardDescription>Atividade do coletor em todas as fontes e perfis; estes valores não são exclusivos da USIAR.</CardDescription></CardHeader><CardContent><dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><CompactMetric label="Registros coletados" value={data.records_collected} /><CompactMetric label="Processos descobertos" value={data.processes_first_seen} /><CompactMetric label="Documentos descobertos" value={data.documents_discovered} /><CompactMetric label="Rodadas" value={data.rounds_total} /><CompactMetric label="Com sucesso" value={data.rounds_success} /><CompactMetric label="Parciais" value={data.rounds_partial} /><CompactMetric label="Com falha" value={data.rounds_failed} /></dl></CardContent></Card>
      <Card><CardHeader><CardTitle>Atividade do perfil</CardTitle><CardDescription>Avaliações, resoluções e decisões registradas para o perfil consultado.</CardDescription></CardHeader><CardContent><dl className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1"><CompactMetric label="Avaliações documentais" value={data.document_screenings_total} /><CompactMetric label="Resoluções operacionais" value={data.operational_resolutions_total} /><CompactMetric label="Revisões humanas" value={data.human_reviews_total} /></dl></CardContent></Card>
    </div>
  </section>;
}
