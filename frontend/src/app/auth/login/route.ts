import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/server/auth/supabase";
import { readEnvironment } from "@/lib/server/env";
import { withDatabase } from "@/lib/server/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function POST(request: Request) {
  const env = readEnvironment();
  if (request.headers.get("origin") !== env.APP_ORIGIN) return new Response(null, { status: 403 });
  const form = await request.formData();
  const email = form.get("email"); const password = form.get("password");
  if (typeof email !== "string" || typeof password !== "string" || email.length > 320 || password.length > 128) {
    return NextResponse.redirect(new URL("/login?error=authentication", env.APP_ORIGIN), 303);
  }
  const { data, error } = await (await createSupabaseServerClient()).auth.signInWithPassword({ email: email.trim().toLowerCase(), password });
  if (error || !data.user?.email) return NextResponse.redirect(new URL("/login?error=authentication", env.APP_ORIGIN), 303);
  const allowed = await withDatabase(async (db) => (await db.query("SELECT 1 FROM app_admins WHERE user_id=$1 AND email=$2 AND active=true", [data.user.id, data.user.email!.toLowerCase()])).rowCount === 1);
  if (!allowed) {
    await (await createSupabaseServerClient()).auth.signOut();
    return NextResponse.redirect(new URL("/login?error=authorization", env.APP_ORIGIN), 303);
  }
  return NextResponse.redirect(new URL("/dashboard", env.APP_ORIGIN), 303);
}
