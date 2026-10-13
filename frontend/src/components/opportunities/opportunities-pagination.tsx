import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { opportunitiesHref, type OpportunityFilter } from "@/lib/opportunities/query";
import type { PaginationResponse } from "@/lib/server/api/contracts.generated";

export function OpportunitiesPagination({ pagination, filter }: { pagination: PaginationResponse; filter: OpportunityFilter }) {
  const hasPrevious = pagination.page > 1;
  const hasNext = pagination.page < pagination.total_pages;
  return <div className="flex flex-col gap-3 rounded-xl border bg-background p-4 text-sm shadow-sm sm:flex-row sm:items-center sm:justify-between">
    <p className="text-muted-foreground">
      Página <strong className="text-foreground">{pagination.page}</strong> de <strong className="text-foreground">{Math.max(pagination.total_pages, 1)}</strong>
      <span className="ml-2">· {pagination.total_items} {pagination.total_items === 1 ? "resultado" : "resultados"}</span>
    </p>
    <div className="flex gap-2">
      {hasPrevious ? <Button asChild variant="outline"><Link href={opportunitiesHref(filter, pagination.page - 1)}><ChevronLeft className="size-4" aria-hidden="true" />Anterior</Link></Button> : <Button variant="outline" disabled><ChevronLeft className="size-4" aria-hidden="true" />Anterior</Button>}
      {hasNext ? <Button asChild variant="outline"><Link href={opportunitiesHref(filter, pagination.page + 1)}>Próxima<ChevronRight className="size-4" aria-hidden="true" /></Link></Button> : <Button variant="outline" disabled>Próxima<ChevronRight className="size-4" aria-hidden="true" /></Button>}
    </div>
  </div>;
}
