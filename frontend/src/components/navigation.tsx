"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Search, ListChecks, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { href: "/dashboard", title: "Dashboard", icon: LayoutDashboard },
  { href: "/opportunities", title: "Oportunidades", icon: Search },
  { href: "/review-queue", title: "Fila de Revisão", icon: ListChecks },
  { href: "/collection-rounds", title: "Rodadas de Coleta", icon: Layers },
];
export function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return <nav aria-label="Navegação principal" className="space-y-2">{items.map(({ href, title, icon: Icon }) =>
    <Link key={href} href={href} onClick={onNavigate} aria-current={pathname === href ? "page" : undefined}
      className={cn("flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring", pathname === href ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
      <Icon className="size-5 shrink-0" aria-hidden="true" />{title}
    </Link>)}</nav>;
}
