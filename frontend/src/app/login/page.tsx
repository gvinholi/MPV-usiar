import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cookieSettings, getAuthRuntime } from "@/lib/server/auth/session";
import { readEnvironment } from "@/lib/server/env";
import { Button } from "@/components/ui/button";
import { InternalLoginForm } from "@/components/login/internal-login-form";

export const dynamic = "force-dynamic";
export default async function Login({ searchParams }: { searchParams: Promise<{ error?: string | string[] }> }) {
  let available = false; let csrf: string | undefined; let mode: "internal" | "oidc" | undefined;
  try {
    const env = readEnvironment(); mode = env.AUTH_MODE;
    const id = (await cookies()).get(cookieSettings(env, "login", 0).name)?.value;
    if (mode === "internal") {
      available = env.configured;
      if (id && /^[A-Za-z0-9_-]{43}$/.test(id)) csrf = id;
    } else {
      const auth = getAuthRuntime();
      available = auth.env.configured;
      const tx = id ? await auth.store.readTransaction(id) : undefined;
      if (tx && !tx.state) csrf = tx.csrf;
    }
  } catch { /* Fail closed; configuration details never reach the browser. */ }
  const rawError = (await searchParams).error;
  const error = typeof rawError === "string" ? rawError : undefined;
  if (available && mode === "internal" && !csrf) redirect(error === "session" ? "/auth/login?error=session" : "/auth/login");
  const message = error === "rate-limited" ? "Muitas tentativas. Aguarde antes de tentar novamente." :
    error === "unavailable" ? "Autenticação temporariamente indisponível. Tente novamente." :
    error === "session" ? "Sua sessão expirou ou foi encerrada. Entre novamente." :
    error === "authentication" && mode === "oidc" ? "Não foi possível concluir a autenticação. Inicie uma nova tentativa." :
    error === "authentication" ? "Não foi possível entrar. Verifique suas credenciais e tente novamente." : undefined;
  return <main className="flex min-h-screen items-center justify-center bg-muted/40 p-6"><section className="w-full max-w-md rounded-2xl border bg-background p-8 shadow-sm sm:p-10">
    <p className="mb-10 text-sm font-bold tracking-[0.25em] text-primary">USIAR</p><h1 className="text-2xl font-semibold tracking-tight">Seu espaço de análise</h1>
    <p className="mb-8 mt-3 text-sm leading-6 text-muted-foreground">Acompanhe oportunidades e organize a revisão da sua equipe.</p>
    {message && <p role="alert" className="mb-5 rounded-lg bg-muted p-4 text-sm leading-6">{message}</p>}
    {!available ? <div role="status" className="rounded-lg bg-muted p-4 text-sm leading-6">Autenticação indisponível. O acesso será liberado após a configuração segura do serviço.</div> : mode === "internal" && csrf ?
      <InternalLoginForm csrf={csrf} /> : csrf ?
      <form action="/auth/login" method="post"><input type="hidden" name="csrf" value={csrf} /><Button type="submit" className="w-full">Entrar com sua organização</Button></form> :
      <Button asChild className="w-full"><a href="/auth/login">Preparar acesso seguro</a></Button>}
    <p className="mt-8 border-t pt-5 text-xs leading-5 text-muted-foreground">Acesso restrito a pessoas autorizadas.</p>
  </section></main>;
}
