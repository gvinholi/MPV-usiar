import type { SourceCoverageResponse } from "@/lib/server/api/contracts.generated";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageState } from "@/components/page-state";
import { formatInteger } from "./metric-card";

export function SourceCoverage({ sources }: { sources: SourceCoverageResponse[] }) {
  if (sources.length === 0) return <section aria-labelledby="coverage-title" className="space-y-4"><div><h2 id="coverage-title" className="text-xl font-semibold">Cobertura por fonte</h2><p className="mt-1 text-sm text-muted-foreground">Métricas gerais da coleta no período.</p></div><PageState title="Nenhuma fonte no período" description="A API não retornou rodadas de coleta para o intervalo selecionado." /></section>;
  return <Card aria-labelledby="coverage-title">
    <CardHeader><CardTitle id="coverage-title">Cobertura por fonte</CardTitle><CardDescription>Métricas gerais da coleta no período, sem restrição ao perfil consultado. O total de rodadas pode incluir estados não detalhados nesta resposta.</CardDescription></CardHeader>
    <CardContent><div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[52rem] border-collapse text-left text-sm"><caption className="sr-only">Cobertura geral da coleta agrupada por fonte</caption><thead className="bg-muted/60"><tr>{["Fonte", "Rodadas", "Sucesso", "Parciais", "Falhas", "Registros", "Processos únicos"].map(label => <th key={label} scope="col" className="px-4 py-3 font-semibold">{label}</th>)}</tr></thead><tbody>{sources.map(source => <tr key={source.source} className="border-t"><th scope="row" className="px-4 py-3 font-medium">{source.source}</th>{[source.rounds, source.successful_rounds, source.partial_rounds, source.failed_rounds, source.records_collected, source.unique_processes].map((value, index) => <td key={index} className="px-4 py-3 tabular-nums">{formatInteger(value)}</td>)}</tr>)}</tbody></table></div></CardContent>
  </Card>;
}
