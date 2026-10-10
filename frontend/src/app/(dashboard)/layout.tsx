import { requireSession } from "@/lib/server/auth/guard";
import { AppShell } from "@/components/app-shell";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();
  return <AppShell csrf={session.browserCsrf}>{children}</AppShell>;
}
