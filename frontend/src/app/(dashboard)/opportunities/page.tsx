import Link from "next/link";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { PageState } from "@/components/page-state";
import { OpportunityFilters } from "@/components/opportunities/opportunity-filters";
import { OpportunitiesPagination } from "@/components/opportunities/opportunities-pagination";
import { OpportunitiesTable } from "@/components/opportunities/opportunities-table";
import { RetryButton } from "@/components/opportunities/retry-button";
import {
  configuredUsiarV2Profile,
  operationalStates,
  OPPORTUNITIES_PAGE_SIZE,
  parseOpportunitiesUrlQuery,
  type RawOpportunitySearchParams,
} from "@/lib/opportunities/query";
import { createApiClient } from "@/lib/server/api/client";
import { ApiError } from "@/lib/server/api/errors";
import { requireSession } from "@/lib/server/auth/guard";
import type { OpportunityListItemResponse, PageResponse } from "@/lib/server/api/contracts.generated";

function Introduction() {
  return <header>
    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-primary">USIAR / Análise</p>
    <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Oportunidades</h1>
    <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
      Licitações candidatas e pendentes para manutenção, higienização e serviços relacionados a climatização em São Paulo.
    </p>
  </header>;
}

function ErrorState({ error }: { error?: ApiError }) {
  const description = error?.status === 404
    ? "O perfil USIAR/v2 ainda não foi persistido pela coleta."
    : error?.message ?? "Serviço temporariamente indisponível.";
  return <div className="space-y-4">
    <PageState error title="Não foi possível consultar oportunidades" description={description} requestId={error?.requestId} />
    <RetryButton />
  </div>;
}

export default async function OpportunitiesPage({ searchParams }: { searchParams: Promise<RawOpportunitySearchParams> }) {
  const session = await requireSession();
  const parsed = parseOpportunitiesUrlQuery(await searchParams);
  if (!parsed.success) return <div className="space-y-6"><Introduction /><PageState error title="Filtros inválidos" description="Use somente os filtros e números de página disponíveis nesta tela." /><Button asChild variant="outline"><Link href="/opportunities">Limpar parâmetros</Link></Button></div>;

  const profile = configuredUsiarV2Profile(session.env);
  if (!profile) return <div className="space-y-6"><Introduction /><PageState error title="Perfil USIAR/v2 não configurado" description="Configure API_PROFILE_ID com o UUID oficial de USIAR/v2 e deixe API_PROFILE_CODE vazio no ambiente do servidor Next.js." /></div>;

  let result: PageResponse<OpportunityListItemResponse>;
  try {
    result = await createApiClient(session.env, session.credential).listOpportunities({
      ...profile,
      operational_state: operationalStates(parsed.data.state),
      page: parsed.data.page,
      page_size: OPPORTUNITIES_PAGE_SIZE,
      sort: "publication_at",
      direction: "DESC",
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect("/login?error=session");
    return <div className="space-y-6"><Introduction /><ErrorState error={error instanceof ApiError ? error : undefined} /></div>;
  }

  const emptyDatabase = parsed.data.state === "all" && parsed.data.page === 1 && result.pagination.total_items === 0;
  return <div className="space-y-6">
    <Introduction />
    <OpportunityFilters active={parsed.data.state} />
    {result.items.length === 0 ? <PageState
      title={emptyDatabase ? "Nenhuma oportunidade coletada" : "Nenhum resultado nesta página"}
      description={emptyDatabase
        ? "O banco ainda não possui oportunidades candidatas ou pendentes para USIAR/v2. Execute a primeira coleta antes de consultar esta tela."
        : "Não há oportunidades para este filtro e página. Ajuste o filtro ou retorne à página anterior."}
    /> : <OpportunitiesTable items={result.items} />}
    <OpportunitiesPagination pagination={result.pagination} filter={parsed.data.state} />
  </div>;
}
