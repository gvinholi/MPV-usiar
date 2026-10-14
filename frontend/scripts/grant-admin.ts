import { readFileSync } from "node:fs";
import { createClient } from "@supabase/supabase-js";
import { Client } from "pg";

// Uso: npm run admin:grant -- admin@exemplo.com [--check]
// --check só localiza o usuário no Supabase Auth e confere a conexão ao banco; não grava.
// DATABASE_URL é a credencial ADMINISTRATIVA. Para o Supabase, DATABASE_CA_CERT aponta para
// a CA do projeto (prod-ca-2021.crt): o pooler usa CA privada e o TLS é sempre verificado.
const args = process.argv.slice(2);
const check = args.includes("--check");
const email = args.find((arg) => !arg.startsWith("--"))?.trim().toLowerCase();
const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL, DATABASE_CA_CERT } = process.env;
if (!email || !SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !DATABASE_URL) {
  console.error("Uso: npm run admin:grant -- admin@exemplo.com [--check] (configure SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL e DATABASE_CA_CERT fora do Git)");
  process.exit(2);
}
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false, autoRefreshToken: false } });
let page = 1; let user: { id: string; email?: string; email_confirmed_at?: string | null } | undefined;
while (!user) {
  const { data, error } = await supabase.auth.admin.listUsers({ page, perPage: 100 });
  if (error) throw new Error("Falha ao consultar o Supabase Auth.");
  user = data.users.find((item) => item.email?.toLowerCase() === email);
  if (user || data.users.length < 100) break;
  page++;
}
if (!user) throw new Error("Usuário não encontrado. Crie-o manualmente no Supabase Auth sem compartilhar a senha.");

const url = new URL(DATABASE_URL);
const local = ["localhost", "127.0.0.1", "::1", "[::1]"].includes(url.hostname);
// sslmode na URL faria o pg reinterpretar o TLS; a política fica explícita abaixo.
url.searchParams.delete("sslmode"); url.searchParams.delete("sslrootcert");
const ssl = local ? false : { rejectUnauthorized: true, ...(DATABASE_CA_CERT ? { ca: readFileSync(DATABASE_CA_CERT, "utf8") } : {}) };
const db = new Client({ connectionString: url.toString(), ssl, application_name: "usiar-admin-grant" });
await db.connect();
try {
  const current = await db.query("SELECT active FROM app_admins WHERE user_id=$1", [user.id]);
  const status = current.rowCount ? (current.rows[0].active ? "já é administrador ativo" : "administrador inativo") : "ainda não é administrador";
  if (check) {
    console.log(`Usuário encontrado (e-mail ${user.email_confirmed_at ? "confirmado" : "NÃO confirmado"}); ${status}. Nada foi gravado (--check).`);
  } else {
    await db.query("INSERT INTO app_admins(user_id,email,active) VALUES($1,$2,true) ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,active=true", [user.id, email]);
    console.log(`Acesso administrativo concedido ao usuário existente (antes: ${status}).`);
  }
} finally { await db.end(); }
