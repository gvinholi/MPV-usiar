import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/server/auth/supabase";
import { readEnvironment } from "@/lib/server/env";

export async function POST(request: Request) {
  const env = readEnvironment();
  if (request.headers.get("origin") !== env.APP_ORIGIN) return new Response(null, { status: 403 });
  const password = (await request.formData()).get("password");
  if (typeof password !== "string" || password.length < 15 || password.length > 128) return NextResponse.redirect(new URL("/update-password?error=1", env.APP_ORIGIN), 303);
  const { error } = await (await createSupabaseServerClient()).auth.updateUser({ password });
  return NextResponse.redirect(new URL(error ? "/update-password?error=1" : "/update-password?done=1", env.APP_ORIGIN), 303);
}
