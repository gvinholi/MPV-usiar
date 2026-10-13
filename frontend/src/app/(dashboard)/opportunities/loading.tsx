import { Skeleton } from "@/components/ui/skeleton";

export default function OpportunitiesLoading() {
  return <div role="status" aria-label="Carregando oportunidades" className="space-y-6">
    <div className="space-y-3"><Skeleton className="h-4 w-28" /><Skeleton className="h-10 w-64 max-w-full" /><Skeleton className="h-5 w-[32rem] max-w-full" /></div>
    <div className="flex gap-2"><Skeleton className="h-10 w-44" /><Skeleton className="h-10 w-40" /><Skeleton className="h-10 w-40" /></div>
    <Skeleton className="h-96 w-full" />
    <span className="sr-only">Carregando a tabela de oportunidades</span>
  </div>;
}
