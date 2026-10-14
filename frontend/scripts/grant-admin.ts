import { createClient } from "@supabase/supabase-js";
import { Client } from "pg";

const email = process.argv[2]?.trim().toLowerCase();
const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL } = process.env;
if (!email || !SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !DATABASE_URL) {
  console.error("Uso: npm run admin:grant -- admin@exemplo.com (configure SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY e DATABASE_URL fora do Git)");
  process.exit(2);
}
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false, autoRefreshToken: false } });
let page = 1; let user: { id: string; email?: string } | undefined;
while (!user) {
  const { data, error } = await supabase.auth.admin.listUsers({ page, perPage: 100 });
  if (error) throw error;
  user = data.users.find((item) => item.email?.toLowerCase() === email);
  if (user || data.users.length < 100) break;
  page++;
}
if (!user) throw new Error("Usuário não encontrado. Crie-o manualmente no Supabase Auth sem compartilhar a senha.");
const db = new Client({ connectionString: DATABASE_URL, ssl: new URL(DATABASE_URL).hostname === "localhost" ? false : { rejectUnauthorized: true } });
await db.connect();
try {
  await db.query("INSERT INTO app_admins(user_id,email,active) VALUES($1,$2,true) ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,active=true", [user.id, email]);
  console.log("Acesso administrativo concedido ao usuário existente.");
} finally { await db.end(); }
