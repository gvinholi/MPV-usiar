import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
  return <div role="status" aria-label="Carregando dashboard" className="space-y-8">
    <div className="space-y-3"><Skeleton className="h-3 w-32" /><Skeleton className="h-10 w-80 max-w-full" /><Skeleton className="h-5 w-[36rem] max-w-full" /></div>
    <Skeleton className="h-28 w-full" />
    <Skeleton className="h-48 w-full" />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-40" />)}</div>
    <div className="grid gap-4 xl:grid-cols-3">{Array.from({ length: 3 }, (_, index) => <Skeleton key={index} className="h-72" />)}</div>
    <span className="sr-only">Carregando dados operacionais</span>
  </div>;
}
