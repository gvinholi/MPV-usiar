import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/server/auth/supabase";
import { readEnvironment } from "@/lib/server/env";

export async function POST(request: Request) {
  const env = readEnvironment();
  if (request.headers.get("origin") !== env.APP_ORIGIN) return new Response(null, { status: 403 });
  const email = (await request.formData()).get("email");
  if (typeof email === "string" && email.length <= 320) {
    await (await createSupabaseServerClient()).auth.resetPasswordForEmail(email.trim().toLowerCase(), { redirectTo: `${env.APP_ORIGIN}/auth/callback` });
  }
  return NextResponse.redirect(new URL("/forgot-password?sent=1", env.APP_ORIGIN), 303);
}
