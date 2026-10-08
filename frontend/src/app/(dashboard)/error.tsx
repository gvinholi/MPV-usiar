"use client";
import { PageState } from "@/components/page-state";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <div className="space-y-4"><PageState error title="Não foi possível carregar esta área" description="Tente novamente em alguns instantes." /><Button onClick={reset}>Tentar novamente</Button></div>;
}
