import "server-only";
import { createHash } from "node:crypto";
import { redirect } from "next/navigation";
import { type BearerCredential } from "../api/client";
import { withDatabase } from "../db";
import { readEnvironment } from "../env";
import { createSupabaseServerClient } from "./supabase";

export async function requireSession() {
  const env = readEnvironment();
  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user?.email) redirect("/login?error=session");
  const email = data.user.email.toLowerCase();
  const authorized = await withDatabase(async (db) => {
    const result = await db.query("SELECT 1 FROM app_admins WHERE user_id=$1 AND email=$2 AND active=true", [data.user.id, email]);
    return result.rowCount === 1;
  });
  if (!authorized) redirect("/login?error=authorization");
  const credential: BearerCredential = {
    async read() { return data.user.id; },
    async invalidate() { await supabase.auth.signOut(); },
  };
  const browserCsrf = createHash("sha256").update(`${data.user.id}:${data.user.updated_at ?? ""}`).digest("base64url");
  return { env, mode: "supabase" as const, credential, browserCsrf, user: data.user };
}

export async function requireDashboard(): Promise<{ message: string; requestId?: string } | undefined> {
  await requireSession();
  return undefined;
}
