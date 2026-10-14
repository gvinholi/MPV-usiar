import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default async function UpdatePassword({ searchParams }: { searchParams: Promise<{ done?: string; error?: string }> }) {
  const query = await searchParams;
  return <main className="flex min-h-screen items-center justify-center bg-muted/40 p-6"><section className="w-full max-w-md rounded-2xl border bg-background p-8 shadow-sm">
    <h1 className="text-2xl font-semibold">Definir nova senha</h1>
    {query.done === "1" ? <><p className="my-5 text-sm">Senha atualizada.</p><Button asChild className="w-full"><a href="/dashboard">Continuar</a></Button></> : <form action="/auth/update-password" method="post" className="mt-6 space-y-4">
      {query.error && <p role="alert" className="text-sm">Use uma senha válida com pelo menos 15 caracteres.</p>}<Label htmlFor="password">Nova senha</Label><Input id="password" name="password" type="password" minLength={15} maxLength={128} required autoComplete="new-password" /><Button className="w-full">Atualizar senha</Button>
    </form>}
  </section></main>;
}
