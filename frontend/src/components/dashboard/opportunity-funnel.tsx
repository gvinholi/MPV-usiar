import type { PilotFunnelResponse } from "@/lib/server/api/contracts.generated";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CompactMetric } from "./metric-card";

export function OpportunityFunnel({ data }: { data: PilotFunnelResponse }) {
  const stages = [
    { title: "Entrada da coleta", description: "Volume geral coletado no período; não é exclusivo do perfil.", values: [["Registros coletados", data.records_collected]] as const },
    { title: "Coorte do perfil", description: "Processos únicos pertencentes à coorte consultada.", values: [["Processos únicos", data.unique_processes]] as const },
    { title: "Triagem inicial", description: "Resultado inicial específico do perfil.", values: [["Candidatos", data.initial_candidate], ["Pendentes", data.initial_pending], ["Descartados", data.initial_discarded]] as const },
    { title: "Avaliação documental", description: "Processos da coorte com avaliação documental.", values: [["Avaliados", data.document_evaluated]] as const },
    { title: "Resolução operacional", description: "Estado operacional vigente específico do perfil.", values: [["Candidatos", data.operational_candidate], ["Pendentes", data.operational_pending], ["Descartados", data.operational_discarded]] as const },
    { title: "Decisão humana", description: "Decisão humana vigente específica do perfil.", values: [["Selecionados", data.selected], ["Pendentes", data.human_pending], ["Descartados", data.human_discarded]] as const },
  ];
  return <Card aria-labelledby="funnel-title">
    <CardHeader><CardTitle id="funnel-title">Funil de oportunidades</CardTitle><CardDescription>Valores absolutos fornecidos pela API. Os estágios possuem bases distintas e não representam taxas de conversão.</CardDescription></CardHeader>
    <CardContent><ol className="space-y-3">{stages.map((stage, index) => <li key={stage.title} className="grid gap-4 rounded-xl border-l-4 border-l-primary bg-muted/20 p-4 md:grid-cols-[minmax(12rem,0.8fr)_2fr] md:items-center">
      <div className="flex gap-3"><span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground" aria-hidden="true">{index + 1}</span><div><h3 className="font-semibold">{stage.title}</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">{stage.description}</p></div></div>
      <dl className="grid gap-2 sm:grid-cols-3">{stage.values.map(([label, value]) => <CompactMetric key={label} label={label} value={value} />)}</dl>
    </li>)}</ol></CardContent>
  </Card>;
}
