import "server-only";
import { getCloudflareContext } from "@opennextjs/cloudflare";
import { Client, type QueryResultRow } from "pg";
import { endQuietly, isWorkersRuntime, postgresConfig, type DatabaseBindings } from "./database-config";
import { readEnvironment } from "./env";

function hyperdriveBinding(): DatabaseBindings["HYPERDRIVE"] {
  // Fora do Worker (vitest, next start em Node) não há contexto Cloudflare.
  try { return (getCloudflareContext().env as Partial<CloudflareEnv>).HYPERDRIVE; }
  catch { return undefined; }
}

function connectionConfig(connectionString?: string) {
  const environment = readEnvironment();
  if (connectionString) return postgresConfig({ DATABASE_URL: connectionString }, { applicationName: "usiar-worker", requireHyperdrive: false });
  return postgresConfig({ HYPERDRIVE: hyperdriveBinding(), DATABASE_URL: environment.DATABASE_URL },
    { applicationName: "usiar-worker", requireHyperdrive: environment.production || isWorkersRuntime() });
}

export async function withDatabase<T>(operation: (client: Client) => Promise<T>, connectionString?: string): Promise<T> {
  const client = new Client(connectionConfig(connectionString));
  const end = endQuietly(client);
  try { await client.connect(); return await operation(client); }
  finally { await end(); }
}

export function jsonRows<T extends QueryResultRow>(rows: T[]): T[] {
  return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [
    key, value instanceof Date ? value.toISOString() : typeof value === "bigint" ? Number(value) : value,
  ])) as T);
}
