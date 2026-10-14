"use client";
import { useState } from "react";
import { Menu, LogOut } from "lucide-react";
import { Navigation } from "./navigation";
import { Button } from "./ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "./ui/sheet";

function Brand() {
  return <div className="mb-10 flex items-center gap-3"><span className="flex size-10 items-center justify-center rounded-xl bg-primary text-lg font-bold text-white">U</span><div><p className="text-lg font-bold tracking-wide">USIAR</p><p className="text-xs text-muted-foreground">Inteligência em licitações</p></div></div>;
}
export function AppShell({ children, csrf: _csrf }: { children: React.ReactNode; csrf: string }) {
  void _csrf;
  const [open, setOpen] = useState(false);
  return <div className="min-h-screen bg-muted/30">
    <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:z-50 focus:bg-background focus:p-4">Ir para o conteúdo</a>
    <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r bg-background p-6 md:flex"><Brand /><Navigation /><p className="mt-auto text-xs leading-5 text-muted-foreground">Coleta e análise de oportunidades.<br />Decisões com revisão humana.</p></aside>
    <div className="md:pl-64">
      <header className="flex min-h-20 items-center justify-between gap-3 border-b bg-background px-4 sm:px-8">
        <div className="flex items-center gap-3">
          <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="ghost" size="icon" className="md:hidden" aria-label="Abrir menu"><Menu className="size-5" /></Button></SheetTrigger>
            <SheetContent><SheetTitle className="mb-1 text-xl font-bold">USIAR</SheetTitle><SheetDescription className="mb-8 text-sm text-muted-foreground">Navegação do painel</SheetDescription><Navigation onNavigate={() => setOpen(false)} /></SheetContent>
          </Sheet><div><p className="text-xs uppercase tracking-widest text-muted-foreground">Área de trabalho</p><p className="font-semibold">Painel de oportunidades</p></div>
        </div>
        <form method="post" action="/auth/logout"><Button type="submit" variant="outline"><LogOut className="size-4" aria-hidden="true" />Sair</Button></form>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-7xl p-5 outline-none sm:p-8 lg:p-10">{children}</main>
    </div>
  </div>;
}
