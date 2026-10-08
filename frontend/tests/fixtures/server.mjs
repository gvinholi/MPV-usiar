// Test-only HTTPS identity provider and API. Never imported by src/ or a production entrypoint.
import https from "node:https";
import http from "node:http";
import { mkdir, writeFile } from "node:fs/promises";
import { createHash, randomBytes } from "node:crypto";
import { generate } from "selfsigned";
import { exportJWK, generateKeyPair, SignJWT, jwtVerify } from "jose";

const tls = await generate([{ name: "commonName", value: "localhost" }], {
  keySize: 2048, algorithm: "sha256",
  extensions: [
    { name: "basicConstraints", cA: true },
    { name: "keyUsage", digitalSignature: true, keyEncipherment: true, keyCertSign: true },
    { name: "subjectAltName", altNames: [{ type: 2, value: "localhost" }, { type: 7, ip: "127.0.0.1" }] },
  ],
});
await mkdir(".test-tls", { recursive: true });
// Only a public certificate is written. Private key lives in this test process.
await writeFile(".test-tls/ca.pem", tls.cert);
const issuer = "https://127.0.0.1:4443";
const keys = await generateKeyPair("RS256");
const jwk = { ...await exportJWK(keys.publicKey), kid: "test-key", alg: "RS256", use: "sig" };
const codes = new Map();
let permission = "dashboard:read";
let scenario = "reader";
const json = (res, value, status = 200) => { res.writeHead(status, { "Content-Type": "application/json" }); res.end(JSON.stringify(value)); };
const bodyOf = async req => { let body = ""; for await (const chunk of req) body += chunk; return body; };
const provider = https.createServer({ key: tls.private, cert: tls.cert }, async (req, res) => {
  try {
    const url = new URL(req.url, issuer);
    if (url.pathname === "/.well-known/openid-configuration") return json(res, {
      issuer, authorization_endpoint: `${issuer}/authorize`, token_endpoint: `${issuer}/token`, jwks_uri: `${issuer}/jwks`,
      response_types_supported: ["code"], subject_types_supported: ["public"], id_token_signing_alg_values_supported: ["RS256"], code_challenge_methods_supported: ["S256"],
    });
    if (url.pathname === "/jwks") return json(res, { keys: [jwk] });
    if (url.pathname === "/authorize") {
      if (url.searchParams.get("client_id") !== "test-client" || url.searchParams.get("redirect_uri") !== "http://127.0.0.1:3100/auth/callback" || url.searchParams.get("code_challenge_method") !== "S256") return json(res, {}, 400);
      const code = randomBytes(24).toString("hex");
      codes.set(code, { challenge: url.searchParams.get("code_challenge"), nonce: url.searchParams.get("nonce"), permission });
      const callback = new URL(url.searchParams.get("redirect_uri"));
      callback.searchParams.set("code", code); callback.searchParams.set("state", url.searchParams.get("state"));
      res.writeHead(302, { Location: callback.href }); return res.end();
    }
    if (url.pathname === "/token" && req.method === "POST") {
      const body = new URLSearchParams(await bodyOf(req)); const tx = codes.get(body.get("code")); codes.delete(body.get("code"));
      const credentials = Buffer.from((req.headers.authorization ?? "").replace(/^Basic /i, ""), "base64").toString("utf8")
        .split(":").map(value => decodeURIComponent(value.replace(/\+/g, " ")));
      if (!tx || body.get("redirect_uri") !== "http://127.0.0.1:3100/auth/callback" ||
        credentials[0] !== "test-client" || credentials[1] !== "test-only-secret" ||
        createHash("sha256").update(body.get("code_verifier") ?? "").digest("base64url") !== tx.challenge) return json(res, { error: "invalid_grant" }, 400);
      const sign = (payload, audience) => new SignJWT(payload).setProtectedHeader({ alg: "RS256", kid: "test-key" })
        .setIssuer(issuer).setSubject("test-user").setAudience(audience).setIssuedAt().setExpirationTime("5m").sign(keys.privateKey);
      return json(res, { token_type: "Bearer", expires_in: 300,
        access_token: await sign({ scope: tx.permission, marker: "test-access-marker" }, "test-api"),
        id_token: await sign({ nonce: tx.nonce }, "test-client"),
      });
    }
    return json(res, {}, 404);
  } catch { return json(res, { error: "fixture failure" }, 500); }
});
const api = http.createServer(async (req, res) => {
  if (req.url === "/health") return json(res, { status: "ok" });
  if (req.url === "/scenario" && req.method === "POST") {
    scenario = await bodyOf(req); permission = scenario === "writer" ? "reviews:write" : "dashboard:read"; return json(res, {});
  }
  const authenticate = async () => {
    if (req.headers.cookie) throw new Error("browser cookie forwarded");
    const token = req.headers.authorization?.replace(/^Bearer /, "");
    const { payload } = await jwtVerify(token, keys.publicKey, { issuer, audience: "test-api" });
    if (!payload.scope.split(" ").includes("dashboard:read")) return false;
    return true;
  };
  if (req.url === "/ready") {
    try {
      if (!await authenticate()) return json(res, { error: { code: "FORBIDDEN" } }, 403);
      return json(res, { status: "ready" });
    } catch { return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401); }
  }
  const url = new URL(req.url, "http://127.0.0.1:8100");
  if (url.pathname === "/api/v1/dashboard/summary") {
    try {
      if (!await authenticate()) return json(res, { error: { code: "FORBIDDEN" } }, 403);
    } catch { return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401); }
    const statuses = { "error-404": 404, "error-409": 409, "error-422": 422, "error-500": 500, "error-503": 503 };
    if (scenario in statuses) return json(res, { error: { code: scenario === "error-409" ? "AMBIGUOUS_PROFILE" : "TEST_ERROR", message: "test-access-marker internal" } }, statuses[scenario]);
    if (url.searchParams.get("profile_code") !== "USIAR" || url.searchParams.has("profile_id")) return json(res, { error: { code: "VALIDATION_ERROR" } }, 422);
    const from = url.searchParams.get("from_datetime"); const to = url.searchParams.get("to_datetime");
    const empty = scenario === "empty";
    const zeroSnapshot = { processes_total: 0, current_candidate: 0, current_pending: 0, current_discarded: 0, needs_review: 0, selected: 0, human_pending: 0, human_discarded: 0, stale_reviews: 0, documents_total: 0, documents_with_artifact: 0, documents_with_text: 0 };
    const zeroActivity = { records_collected: 0, processes_first_seen: 0, documents_discovered: 0, document_screenings_total: 0, operational_resolutions_total: 0, human_reviews_total: 0, rounds_total: 0, rounds_success: 0, rounds_partial: 0, rounds_failed: 0 };
    const zeroFunnel = { records_collected: 0, unique_processes: 0, initial_candidate: 0, initial_pending: 0, initial_discarded: 0, document_evaluated: 0, operational_candidate: 0, operational_pending: 0, operational_discarded: 0, selected: 0, human_pending: 0, human_discarded: 0 };
    return json(res, {
      profile_id: "c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9ad4", period: { from_datetime: from, to_datetime: to },
      current_snapshot: empty ? zeroSnapshot : { ...zeroSnapshot, processes_total: 1, current_candidate: 1, needs_review: 1, documents_total: 2, documents_with_artifact: 1, documents_with_text: 1 },
      period_activity: empty ? zeroActivity : { ...zeroActivity, records_collected: 7, processes_first_seen: 1, documents_discovered: 2, document_screenings_total: 1, operational_resolutions_total: 1, rounds_total: 2, rounds_success: 1, rounds_partial: 1 },
      funnel: empty ? zeroFunnel : { ...zeroFunnel, records_collected: 7, unique_processes: 1, initial_candidate: 1, document_evaluated: 1, operational_candidate: 1 },
      source_coverage: empty ? [] : [{ source: "FONTE-NOVA", rounds: 2, successful_rounds: 1, partial_rounds: 1, failed_rounds: 0, records_collected: 7, unique_processes: 1 }],
    });
  }
  return json(res, {}, 404);
});
provider.listen(4443, "127.0.0.1");
api.listen(8100, "127.0.0.1");
const shutdown = () => { provider.close(); api.close(); };
process.on("SIGTERM", shutdown); process.on("SIGINT", shutdown);
