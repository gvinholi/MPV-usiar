import { describe, expect, it, vi } from "vitest";
import { EventEmitter } from "node:events";
import { DatabaseConfigurationError, endQuietly, isWorkersRuntime, postgresConfig } from "../src/lib/server/database-config";

const options = { applicationName: "test", requireHyperdrive: false };

describe("database connection config", () => {
  it("uses only the Hyperdrive binding when present, without client-side TLS overrides", () => {
    const config = postgresConfig({ HYPERDRIVE: { connectionString: "postgresql://u:p@hd.local:5432/db" }, DATABASE_URL: "postgresql://x@db.test/db" }, { ...options, requireHyperdrive: true });
    expect(config).toEqual({ connectionString: "postgresql://u:p@hd.local:5432/db" });
  });
  it("requires Hyperdrive in production", () => {
    expect(() => postgresConfig({ DATABASE_URL: "postgresql://x@db.test/db" }, { ...options, requireHyperdrive: true })).toThrow(DatabaseConfigurationError);
    expect(() => postgresConfig({}, options)).toThrow(DatabaseConfigurationError);
  });
  it("never disables certificate verification for remote DATABASE_URL", () => {
    expect(postgresConfig({ DATABASE_URL: "postgresql://x@db.test/db" }, options).ssl).toEqual({ rejectUnauthorized: true });
    expect(postgresConfig({ DATABASE_URL: "postgresql://x@127.0.0.1/db" }, options).ssl).toBe(false);
  });
  it("rejects non-PostgreSQL URLs without echoing them", () => {
    expect(() => postgresConfig({ DATABASE_URL: "https://secret@db.test" }, options)).toThrow("DATABASE_NOT_CONFIGURED");
  });
  it("swallows socket errors emitted after end, even when end is replaced by the quiet version", async () => {
    const client = Object.assign(new EventEmitter(), { ended: 0, async end() { this.ended++; } });
    const end = endQuietly(client);
    Object.assign(client, { end });
    await client.end();
    expect(client.ended).toBe(1); // chama o end original uma vez, sem recursão
    expect(() => client.emit("error", new Error("This socket has been closed."))).not.toThrow();
  });
  it("detects the Cloudflare Workers runtime only by its user agent", () => {
    expect(isWorkersRuntime()).toBe(false);
    vi.stubGlobal("navigator", { userAgent: "Cloudflare-Workers" });
    try { expect(isWorkersRuntime()).toBe(true); } finally { vi.unstubAllGlobals(); }
  });
});
