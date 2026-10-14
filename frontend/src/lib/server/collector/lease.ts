import { randomUUID } from "node:crypto";
import type { Client } from "pg";

// Lease persistido (migration 0013) compartilhado com o coletor Python
// (collector/infra/database/operational_run_lock.py). Substitui o advisory lock
// de sessão, que não sobrevive ao pool em modo transação do Hyperdrive.
// Todo horário vem do relógio do banco (clock_timestamp()).

export const PNCP_LEASE = "PNCP_COLLECTION";
export type Lease = { name: string; ownerId: string; ownerKind: string; token: string; lost: boolean };

export class LeaseLostError extends Error {
  constructor() { super("COLLECTION_LEASE_LOST"); }
}

type Queryable = Pick<Client, "query">;

export async function acquireLease(db: Queryable, options: { ownerKind: string; ttlSeconds: number; name?: string }): Promise<Lease | null> {
  const name = options.name ?? PNCP_LEASE; const ownerId = randomUUID();
  const result = await db.query(`UPDATE collection_leases
    SET owner_id=$2, owner_kind=$3, fencing_token=fencing_token+1, acquired_at=clock_timestamp(), heartbeat_at=clock_timestamp(),
        expires_at=clock_timestamp()+make_interval(secs=>$4::double precision), released_at=NULL
    WHERE name=$1 AND (owner_id IS NULL OR expires_at<=clock_timestamp()) RETURNING fencing_token::text token`, [name, ownerId, options.ownerKind, options.ttlSeconds]);
  return result.rowCount ? { name, ownerId, ownerKind: options.ownerKind, token: String(result.rows[0].token), lost: false } : null;
}

export async function renewLease(db: Queryable, lease: Lease, ttlSeconds: number): Promise<boolean> {
  const result = await db.query(`UPDATE collection_leases SET heartbeat_at=clock_timestamp(), expires_at=clock_timestamp()+make_interval(secs=>$4::double precision)
    WHERE name=$1 AND owner_id=$2 AND fencing_token=$3::bigint AND expires_at>clock_timestamp() RETURNING 1`, [lease.name, lease.ownerId, lease.token, ttlSeconds]);
  if (!result.rowCount) lease.lost = true;
  return Boolean(result.rowCount);
}

export async function releaseLease(db: Queryable, lease: Lease): Promise<boolean> {
  const result = await db.query(`UPDATE collection_leases SET owner_id=NULL, owner_kind=NULL, expires_at=NULL, released_at=clock_timestamp()
    WHERE name=$1 AND owner_id=$2 AND fencing_token=$3::bigint RETURNING 1`, [lease.name, lease.ownerId, lease.token]);
  return Boolean(result.rowCount);
}

/**
 * Fencing: a transação começa travando o próprio lease em FOR SHARE. Se ele
 * expirou ou mudou de dono, nada é gravado. Uma tomada de lease (UPDATE) espera
 * esta transação terminar, então uma execução antiga nunca grava depois que
 * outra assumiu. Atrás do Hyperdrive, BEGIN..COMMIT fica numa única conexão.
 */
export async function fenced<T>(db: Queryable, lease: Lease, operation: () => Promise<T>): Promise<T> {
  if (lease.lost) throw new LeaseLostError();
  await db.query("BEGIN");
  try {
    const held = await db.query(`SELECT 1 FROM collection_leases WHERE name=$1 AND owner_id=$2 AND fencing_token=$3::bigint AND expires_at>clock_timestamp() FOR SHARE`,
      [lease.name, lease.ownerId, lease.token]);
    if (!held.rowCount) { lease.lost = true; throw new LeaseLostError(); }
    const value = await operation();
    await db.query("COMMIT");
    return value;
  } catch (error) { try { await db.query("ROLLBACK"); } catch { /* conexão já perdida */ } throw error; }
}

/**
 * Renovação periódica numa conexão própria: a conexão principal pode estar no
 * meio de uma transação, e o pg enfileiraria o UPDATE dentro dela.
 * Falha transitória tenta de novo no ciclo seguinte; se o TTL vencer antes, o
 * fencing barra as gravações. Lease perdido marca `lease.lost` e para.
 */
export function startHeartbeat(connect: () => Promise<Client>, lease: Lease, options: { intervalMs: number; ttlSeconds: number; log: (event: string, fields?: Record<string, unknown>) => void }) {
  let stopped = false; let timer: ReturnType<typeof setTimeout> | undefined; let client: Client | undefined; let running: Promise<void> = Promise.resolve();
  const tick = async () => {
    try {
      client ??= await connect();
      if (!await renewLease(client, lease, options.ttlSeconds)) { options.log("collection_lease_lost", { lease: lease.name, owner_id: lease.ownerId, fencing_token: lease.token }); stopped = true; return; }
    } catch {
      options.log("collection_lease_renew_failed", { lease: lease.name });
      const broken = client; client = undefined; if (broken) await broken.end().catch(() => undefined);
    }
    if (!stopped) timer = setTimeout(() => { running = tick(); }, options.intervalMs);
  };
  timer = setTimeout(() => { running = tick(); }, options.intervalMs);
  return {
    async stop() { stopped = true; if (timer) clearTimeout(timer); await running; await client?.end().catch(() => undefined); },
  };
}

export async function recoverOrphanRounds(db: Queryable, lease: Lease): Promise<string[]> {
  // Com o lease em mãos nenhuma outra coleta está viva: RUNNING é de execução
  // que morreu ou perdeu o lease antes de fechar a própria rodada.
  return fenced(db, lease, async () => (await db.query(`UPDATE collection_rounds SET status='FAILED', finished_at=clock_timestamp(), errors=errors+1
    WHERE source='PNCP' AND status='RUNNING' RETURNING id`)).rows.map((row) => String(row.id)));
}
