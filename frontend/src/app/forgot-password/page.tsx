import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default async function ForgotPassword({ searchParams }: { searchParams: Promise<{ sent?: string }> }) {
  const sent = (await searchParams).sent === "1";
  return <main className="flex min-h-screen items-center justify-center bg-muted/40 p-6"><section className="w-full max-w-md rounded-2xl border bg-background p-8 shadow-sm">
    <h1 className="text-2xl font-semibold">Recuperar senha</h1><p className="my-5 text-sm text-muted-foreground">Informe o e-mail administrativo. Se a conta existir, o Supabase enviará um link seguro.</p>
    {sent ? <p role="status" className="rounded-lg bg-muted p-4 text-sm">Solicitação recebida. Consulte seu e-mail.</p> : <form action="/auth/recover" method="post" className="space-y-4"><Label htmlFor="email">E-mail</Label><Input id="email" name="email" type="email" required /><Button className="w-full">Enviar link</Button></form>}
    <Button asChild variant="ghost" className="mt-4 w-full"><a href="/login">Voltar ao login</a></Button>
  </section></main>;
}
