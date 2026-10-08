import "server-only";
import { createHash, randomBytes } from "node:crypto";

export const randomSecret = () => randomBytes(32).toString("base64url");
const key = (id: string) => createHash("sha256").update(id).digest("hex");

export type LoginTransaction = {
  csrf: string; expiresAt: number;
  state?: string; nonce?: string; verifier?: string;
};
export type Session = {
  accessToken: string; subject: string; csrf: string;
  createdAt: number; lastSeenAt: number; expiresAt: number;
};
export interface SessionStore {
  createTransaction(value: LoginTransaction): Promise<string>;
  readTransaction(id: string): Promise<LoginTransaction | undefined>;
  consumeTransaction(id: string): Promise<LoginTransaction | undefined>;
  createSession(value: Session): Promise<string>;
  readSession(id: string): Promise<Session | undefined>;
  deleteSession(id: string): Promise<void>;
}

/** Single-process local development only. Atomic consume must remain atomic in a shared adapter. */
export class MemorySessionStore implements SessionStore {
  private transactions = new Map<string, LoginTransaction>();
  private sessions = new Map<string, Session>();
  constructor(private idleMs: number, private clock = Date.now, mode = process.env.NODE_ENV) {
    if (mode !== "development" && mode !== "test") throw new Error("Armazenamento de sessão indisponível.");
  }
  private prune() {
    const now = this.clock();
    for (const [id, tx] of this.transactions) if (tx.expiresAt <= now) this.transactions.delete(id);
    for (const [id, session] of this.sessions) {
      if (session.expiresAt <= now || session.lastSeenAt + this.idleMs <= now) this.sessions.delete(id);
    }
  }
  private checkCapacity() {
    this.prune();
    if (this.transactions.size + this.sessions.size >= 10000) throw new Error("Armazenamento de sessão indisponível.");
  }
  async createTransaction(value: LoginTransaction) {
    this.checkCapacity(); const id = randomSecret(); this.transactions.set(key(id), { ...value }); return id;
  }
  async readTransaction(id: string) {
    this.prune(); const value = this.transactions.get(key(id)); return value ? { ...value } : undefined;
  }
  async consumeTransaction(id: string) {
    this.prune(); const hashed = key(id); const value = this.transactions.get(hashed);
    this.transactions.delete(hashed); return value ? { ...value } : undefined;
  }
  async createSession(value: Session) {
    this.checkCapacity(); const id = randomSecret(); this.sessions.set(key(id), { ...value }); return id;
  }
  async readSession(id: string) {
    this.prune(); const value = this.sessions.get(key(id));
    if (!value) return undefined;
    value.lastSeenAt = this.clock(); return { ...value };
  }
  async deleteSession(id: string) { this.sessions.delete(key(id)); }
}
