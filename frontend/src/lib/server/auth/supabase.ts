import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { readEnvironment } from "../env";

export async function createSupabaseServerClient() {
  const env = readEnvironment();
  const jar = await cookies();
  return createServerClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
    cookies: {
      getAll: () => jar.getAll(),
      setAll(items) {
        try {
          for (const { name, value, options } of items) jar.set(name, value, {
            ...options, httpOnly: true, secure: env.production, sameSite: "lax", path: "/",
          });
        } catch { /* Server Components refresh cookies on the next Route Handler request. */ }
      },
    },
  });
}
