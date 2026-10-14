import { randomUUID } from "node:crypto";
import { Client } from "pg";
import { describe, expect, it } from "vitest";
import { persistModalityOutcome, serializeJsonb, type Outcome } from "../src/lib/server/collector/runner";

const emptyErrors: Outcome["mappingErrors"] = [];
const oneError: Outcome["mappingErrors"] = [
  { item_index: 3, message: "INVALID_FIELD_TYPE" },
];
const severalErrors: Outcome["mappingErrors"] = [
  { item_index: 3, message: "INVALID_FIELD_TYPE" },
  { item_index: 17, message: "MISSING_OFFICIAL_ID" },
];

describe("collector JSONB persistence", () => {
  it.each([
    ["an empty list", emptyErrors],
    ["one mapping error", oneError],
    ["several mapping errors", severalErrors],
  ])("serializes %s as a JSON array", (_name, errors) => {
    const serialized = serializeJsonb(errors);
    expect(serialized.startsWith("[")).toBe(true);
    expect(JSON.parse(serialized)).toEqual(errors);
  });

  it("rejects values that JSON cannot represent", () => {
    expect(() => serializeJsonb(undefined)).toThrow("JSONB_SERIALIZATION_FAILED");
  });
});

const testDatabaseUrl = process.env.USIAR_TEST_DATABASE_URL;
const integrationTest = testDatabaseUrl ? it : it.skip;

describe("collector PostgreSQL persistence", () => {
  integrationTest("persists and reads modality metrics with non-empty mapping errors", async () => {
    const url = new URL(testDatabaseUrl!);
    if (!["127.0.0.1", "localhost", "::1", "[::1]"].includes(url.hostname) || url.pathname !== "/usiar_jsonb_validation") {
      throw new Error("USIAR_TEST_DATABASE_URL must target the local disposable usiar_jsonb_validation database");
    }

    const db = new Client({ connectionString: testDatabaseUrl, ssl: false });
    await db.connect();
    await db.query("BEGIN");
    try {
      const roundId = randomUUID();
      const now = new Date().toISOString();
      await db.query(`INSERT INTO collection_rounds(id,source,started_at,status,pages_expected,pages_processed,pages_with_error,records_collected,unique_processes,candidates,selected,pending,discarded,documents_found,errors,created_at)
        VALUES($1,'PNCP',$2,'RUNNING',0,0,0,0,0,0,0,0,0,0,0,$2)`, [roundId, now]);
      const outcomes: Outcome[] = [
        { modality: 6, complete: true, expectedPages: 1, pages: 1, records: 0, mapped: 0, failedPage: null, reason: null, mappingErrors: emptyErrors },
        { modality: 8, complete: false, expectedPages: 3, pages: 3, records: 101, mapped: 100, failedPage: null, reason: null, mappingErrors: oneError },
        { modality: 9, complete: false, expectedPages: 9, pages: 8, records: 375, mapped: 374, failedPage: null, reason: null, mappingErrors: severalErrors },
      ];
      for (const outcome of outcomes) await persistModalityOutcome(db, roundId, outcome, now);
      const result = await db.query(`SELECT modality_code, complete, pages_processed, records_received,
        processes_mapped, failed_page, failure_reason, mapping_errors,
        jsonb_array_length(mapping_errors) AS mapping_errors_count
        FROM collection_modality_outcomes WHERE round_id=$1 ORDER BY modality_code`, [roundId]);

      expect(result.rows).toEqual([
        { modality_code: 6, complete: true, pages_processed: 1, records_received: 0, processes_mapped: 0, failed_page: null, failure_reason: null, mapping_errors: emptyErrors, mapping_errors_count: 0 },
        { modality_code: 8, complete: false, pages_processed: 3, records_received: 101, processes_mapped: 100, failed_page: null, failure_reason: null, mapping_errors: oneError, mapping_errors_count: 1 },
        { modality_code: 9, complete: false, pages_processed: 8, records_received: 375, processes_mapped: 374, failed_page: null, failure_reason: null, mapping_errors: severalErrors, mapping_errors_count: 2 },
      ]);
    } finally {
      await db.query("ROLLBACK").catch(() => undefined);
      await db.end();
    }
  });
});
