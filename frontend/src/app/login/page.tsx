import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { InternalLoginForm } from "@/components/login/internal-login-form";
import { createSupabaseServerClient } from "@/lib/server/auth/supabase";
import { withDatabase } from "@/lib/server/db";

export const dynamic = "force-dynamic";
export default async function Login({ searchParams }: { searchParams: Promise<{ error?: string | string[] }> }) {
  const { data } = await (await createSupabaseServerClient()).auth.getUser();
  if (data.user?.email) {
    const allowed = await withDatabase(async (db) => (await db.query("SELECT 1 FROM app_admins WHERE user_id=$1 AND email=$2 AND active=true", [data.user!.id, data.user!.email!.toLowerCase()])).rowCount === 1);
    if (allowed) redirect("/dashboard");
  }
  const raw = (await searchParams).error; const error = typeof raw === "string" ? raw : undefined;
  const message = error === "session" ? "Sua sessão expirou. Entre novamente." : error === "authorization" ? "Esta conta não possui acesso administrativo." : error ? "Não foi possível entrar. Verifique suas credenciais." : undefined;
  return <main className="flex min-h-screen items-center justify-center bg-muted/40 p-6"><section className="w-full max-w-md rounded-2xl border bg-background p-8 shadow-sm sm:p-10">
    <p className="mb-10 text-sm font-bold tracking-[0.25em] text-primary">USIAR</p><h1 className="text-2xl font-semibold tracking-tight">Seu espaço de análise</h1>
    <p className="mb-8 mt-3 text-sm leading-6 text-muted-foreground">Acesso administrativo protegido pelo Supabase Auth.</p>
    {message && <p role="alert" className="mb-5 rounded-lg bg-muted p-4 text-sm leading-6">{message}</p>}
    <InternalLoginForm csrf="" />
    <Button asChild variant="ghost" className="mt-4 w-full"><a href="/forgot-password">Esqueci minha senha</a></Button>
    <p className="mt-8 border-t pt-5 text-xs leading-5 text-muted-foreground">Não há cadastro público. O acesso é concedido por um administrador.</p>
  </section></main>;
}
