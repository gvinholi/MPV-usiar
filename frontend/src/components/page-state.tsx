import { CircleAlert, Inbox } from "lucide-react";
import { Skeleton } from "./ui/skeleton";
export function PageState({ title, description, error = false, requestId }: { title: string; description: string; error?: boolean; requestId?: string }) {
  const Icon = error ? CircleAlert : Inbox;
  return <section role={error ? "alert" : "status"} className="flex min-h-64 flex-col items-center justify-center rounded-xl border bg-background px-6 py-12 text-center shadow-sm">
    <div className="mb-5 rounded-full bg-muted p-4"><Icon className="size-6 text-muted-foreground" aria-hidden="true" /></div>
    <h2 className="text-lg font-semibold">{title}</h2><p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">{description}</p>
    {requestId && <p className="mt-4 text-xs text-muted-foreground">Referência: {requestId}</p>}
  </section>;
}
export function LoadingState() {
  return <div role="status" aria-label="Carregando" className="space-y-6"><Skeleton className="h-8 w-52" /><Skeleton className="h-4 w-72 max-w-full" /><Skeleton className="h-64 w-full" /><span className="sr-only">Carregando conteúdo</span></div>;
}
