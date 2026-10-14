import type { ClientConfig } from "pg";

// Sem "server-only": também é usado pelo handler scheduled (custom-worker.ts),
// que o wrangler empacota fora das condições do React Server.
export type DatabaseBindings = { HYPERDRIVE?: Pick<Hyperdrive, "connectionString">; DATABASE_URL?: string };

export class DatabaseConfigurationError extends Error {
  constructor() { super("DATABASE_NOT_CONFIGURED"); }
}

const LOCAL_HOSTS = ["localhost", "127.0.0.1", "::1", "[::1]"];

/** No runtime do Cloudflare Workers o banco só pode ser acessado pelo Hyperdrive. */
export function isWorkersRuntime(): boolean {
  return typeof navigator !== "undefined" && navigator.userAgent === "Cloudflare-Workers";
}

/**
 * Produção usa só o Hyperdrive: ele guarda a credencial e faz o TLS até o
 * Supabase com verify-full contra a CA do projeto (o Worker não aceita CA
 * própria em sockets diretos). DATABASE_URL fica para Node local e testes, com
 * verificação de certificado sempre ligada fora de localhost.
 */
export function postgresConfig(bindings: DatabaseBindings, options: { applicationName: string; requireHyperdrive: boolean }): ClientConfig {
  const hyperdrive = bindings.HYPERDRIVE?.connectionString;
  if (hyperdrive) return { connectionString: hyperdrive };
  if (options.requireHyperdrive || !bindings.DATABASE_URL) throw new DatabaseConfigurationError();
  const url = new URL(bindings.DATABASE_URL);
  if (!["postgres:", "postgresql:"].includes(url.protocol) || !url.hostname) throw new DatabaseConfigurationError();
  const local = LOCAL_HOSTS.includes(url.hostname);
  return { connectionString: bindings.DATABASE_URL, ssl: local ? false : { rejectUnauthorized: true }, application_name: options.applicationName };
}

/**
 * pg-cloudflare rejeita o loop de leitura com "This socket has been closed"
 * depois de client.end(); o pg reemite como evento "error" num client já
 * encerrado e, sem listener, vira unhandledRejection no Worker. Ignora só o que
 * chega depois do encerramento; antes disso o erro também rejeita a query em curso.
 */
export function endQuietly(client: { on(event: "error", listener: (error: Error) => void): unknown; end(): Promise<void> }) {
  let ending = false; const end = client.end.bind(client);
  client.on("error", () => { if (!ending) console.error(JSON.stringify({ event: "database_client_error" })); });
  return async () => { ending = true; await end().catch(() => undefined); };
}
