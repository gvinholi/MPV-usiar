import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/server/auth/supabase";
import { readEnvironment } from "@/lib/server/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  const env = readEnvironment(); const code = new URL(request.url).searchParams.get("code");
  if (!code) return NextResponse.redirect(new URL("/login?error=authentication", env.APP_ORIGIN));
  const { error } = await (await createSupabaseServerClient()).auth.exchangeCodeForSession(code);
  return NextResponse.redirect(new URL(error ? "/login?error=authentication" : "/update-password", env.APP_ORIGIN));
}
