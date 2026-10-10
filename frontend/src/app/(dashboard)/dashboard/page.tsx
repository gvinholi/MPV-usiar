import Link from "next/link";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { PageState } from "@/components/page-state";
import { DashboardHeader, DashboardIntroduction } from "@/components/dashboard/dashboard-header";
import { PeriodFilter } from "@/components/dashboard/period-filter";
import { PrimaryIndicators, CurrentSnapshot } from "@/components/dashboard/current-snapshot";
import { OpportunityFunnel } from "@/components/dashboard/opportunity-funnel";
import { CollectionActivity } from "@/components/dashboard/collection-activity";
import { SourceCoverage } from "@/components/dashboard/source-coverage";
import { parseDashboardUrlQuery, configuredDashboardProfile, hasDashboardData, type RawSearchParams } from "@/lib/dashboard/query";
import { createApiClient } from "@/lib/server/api/client";
import { ApiError } from "@/lib/server/api/errors";
import { requireSession } from "@/lib/server/auth/guard";
import type { DashboardSummaryResponse } from "@/lib/server/api/contracts.generated";

function Message({ title, description, requestId, clearFilters = false }: {
  title: string;
  description: string;
  requestId?: string;
  clearFilters?: boolean;
}) {
  return <div className="space-y-5"><DashboardIntroduction /><PageState error title={title} description={description} requestId={requestId} />{clearFilters && <Button asChild variant="outline"><Link href="/dashboard">Limpar parâmetros</Link></Button>}</div>;
}

function errorDescription(error: ApiError) {
  if (error.status === 404) return "O perfil configurado não foi encontrado.";
  if (error.code === "AMBIGUOUS_PROFILE") return "O código configurado identifica mais de uma versão. Configure API_PROFILE_ID.";
  return error.message;
}

export default async function DashboardPage({ searchParams }: { searchParams: Promise<RawSearchParams> }) {
  const session = await requireSession();
  const parsed = parseDashboardUrlQuery(await searchParams);
  if (!parsed.success) return <Message title="Período inválido" description="Use somente limites ISO 8601 válidos, com fuso, e mantenha o início anterior ao fim." clearFilters />;

  const profile = configuredDashboardProfile(session.env);
  if (!profile.success) return <Message title="Perfil não configurado" description="Configure exatamente um API_PROFILE_ID válido ou API_PROFILE_CODE no ambiente do servidor." />;

  let summary: DashboardSummaryResponse;
  try {
    summary = await createApiClient(session.env, session.credential).getDashboardSummary({ ...profile.data, ...parsed.data });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login?error=session");
    if (error instanceof ApiError) return <Message title="Consulta indisponível" description={errorDescription(error)} requestId={error.requestId} />;
    return <Message title="Consulta indisponível" description="Serviço temporariamente indisponível." />;
  }

  return <div className="space-y-8 lg:space-y-10">
    <DashboardHeader profileId={summary.profile_id} configuredCode={profile.data.profile_code} period={summary.period} />
    <PeriodFilter key={`${parsed.data.from_datetime ?? ""}:${parsed.data.to_datetime ?? ""}`} initialFrom={parsed.data.from_datetime} initialTo={parsed.data.to_datetime} />
    {!hasDashboardData(summary) ? <PageState title="Nenhum dado no período" description="A API retornou o resumo sem atividade, processos ou fontes para o intervalo selecionado." /> : <>
      <PrimaryIndicators data={summary.current_snapshot} />
      <CurrentSnapshot data={summary.current_snapshot} />
      <OpportunityFunnel data={summary.funnel} />
      <CollectionActivity data={summary.period_activity} />
      <SourceCoverage sources={summary.source_coverage} />
    </>}
  </div>;
}
