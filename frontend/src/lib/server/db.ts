import "server-only";
import { Client, type QueryResultRow } from "pg";
import { readEnvironment } from "./env";

function connectionConfig(connectionString = readEnvironment().DATABASE_URL) {
  const url = new URL(connectionString);
  const local = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  return { connectionString, ssl: local ? false : { rejectUnauthorized: true }, application_name: "usiar-worker" } as const;
}

export async function withDatabase<T>(operation: (client: Client) => Promise<T>, connectionString?: string): Promise<T> {
  const client = new Client(connectionConfig(connectionString));
  await client.connect();
  try { return await operation(client); }
  finally { await client.end(); }
}

export function jsonRows<T extends QueryResultRow>(rows: T[]): T[] {
  return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [
    key, value instanceof Date ? value.toISOString() : typeof value === "bigint" ? Number(value) : value,
  ])) as T);
}
