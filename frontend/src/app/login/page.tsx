import { cookies } from "next/headers";
import { cookieSettings, getAuthRuntime } from "@/lib/server/auth/session";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";
export default async function Login({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  let available = false; let csrf: string | undefined;
  try {
    const auth = getAuthRuntime(); available = auth.env.configured;
    const id = (await cookies()).get(cookieSettings(auth.env, "login", 0).name)?.value;
    const tx = id ? await auth.store.readTransaction(id) : undefined;
    if (tx && !tx.state) csrf = tx.csrf;
  } catch { /* Fail closed; configuration details never reach the browser. */ }
  const failed = (await searchParams).error === "authentication";
  return <main className="flex min-h-screen items-center justify-center bg-muted/40 p-6"><section className="w-full max-w-md rounded-2xl border bg-background p-8 shadow-sm sm:p-10">
    <p className="mb-10 text-sm font-bold tracking-[0.25em] text-primary">USIAR</p><h1 className="text-2xl font-semibold tracking-tight">Seu espaço de análise</h1>
    <p className="mb-8 mt-3 text-sm leading-6 text-muted-foreground">Acompanhe oportunidades e organize a revisão da sua equipe.</p>
    {failed && <p role="alert" className="mb-5 text-sm">Não foi possível concluir a autenticação. Inicie uma nova tentativa.</p>}
    {!available ? <div role="status" className="rounded-lg bg-muted p-4 text-sm leading-6">Autenticação indisponível. O acesso será liberado após a configuração segura do serviço.</div> : csrf ?
      <form action="/auth/login" method="post"><input type="hidden" name="csrf" value={csrf} /><Button type="submit" className="w-full">Entrar com sua organização</Button></form> :
      <Button asChild className="w-full"><a href="/auth/login">Preparar acesso seguro</a></Button>}
    <p className="mt-8 border-t pt-5 text-xs leading-5 text-muted-foreground">Acesso restrito a pessoas autorizadas.</p>
  </section></main>;
}
