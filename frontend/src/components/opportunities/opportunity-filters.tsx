import Link from "next/link";
import { Button } from "@/components/ui/button";
import { opportunitiesHref, type OpportunityFilter } from "@/lib/opportunities/query";

const filters: { value: OpportunityFilter; label: string }[] = [
  { value: "all", label: "Todas as relevantes" },
  { value: "candidate", label: "Somente candidatas" },
  { value: "pending", label: "Somente pendentes" },
];

export function OpportunityFilters({ active }: { active: OpportunityFilter }) {
  return <nav aria-label="Filtrar oportunidades por classificação" className="flex flex-wrap gap-2">
    {filters.map(filter => <Button key={filter.value} asChild variant={active === filter.value ? "default" : "outline"}>
      <Link href={opportunitiesHref(filter.value)} aria-current={active === filter.value ? "page" : undefined}>
        {filter.label}
      </Link>
    </Button>)}
  </nav>;
}
