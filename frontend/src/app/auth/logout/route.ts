import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/server/auth/supabase";
import { readEnvironment } from "@/lib/server/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function POST(request: Request) {
  const env = readEnvironment();
  if (request.headers.get("origin") !== env.APP_ORIGIN) return new Response(null, { status: 403 });
  await (await createSupabaseServerClient()).auth.signOut();
  return NextResponse.redirect(new URL("/login", env.APP_ORIGIN), 303);
}
