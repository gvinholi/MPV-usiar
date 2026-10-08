import { requireDashboard } from "@/lib/server/auth/guard";
import { PageState } from "./page-state";
export async function FoundationPage({ title, description }: { title: string; description: string }) {
  const error = await requireDashboard();
  return <><div className="mb-8"><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-primary">USIAR / Análise</p><h1 className="text-3xl font-semibold tracking-tight">{title}</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p></div>
    {error ? <PageState title="Consulta indisponível" description={error.message} error requestId={error.requestId} /> :
      <PageState title="Área em preparação" description="Esta área receberá as consultas operacionais nas próximas entregas. Nenhum dado de oportunidade está sendo exibido nesta etapa." />}</>;
}
