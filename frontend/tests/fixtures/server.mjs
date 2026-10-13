// Test-only HTTPS identity provider and API. Never imported by src/ or a production entrypoint.
import https from "node:https";
import http from "node:http";
import { mkdir, writeFile } from "node:fs/promises";
import { createHash, randomBytes, randomUUID } from "node:crypto";
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
const internalSessions = new Map();
let permission = "dashboard:read";
let scenario = "reader";
const usiarV2 = "42227c23-f6ea-5a43-b640-56ed6eb6981c";
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
  if (req.url === "/api/v1/auth/session" && req.method === "POST") {
    if (scenario === "auth-invalid") return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401);
    if (scenario === "auth-rate") { res.setHeader("Retry-After", "30"); return json(res, { error: { code: "AUTHENTICATION_RATE_LIMITED" } }, 429); }
    if (scenario === "auth-unavailable") return json(res, { error: { code: "AUTHENTICATION_UNAVAILABLE" } }, 503);
    let body;
    try { body = JSON.parse(await bodyOf(req)); } catch { return json(res, { error: { code: "VALIDATION_ERROR" } }, 422); }
    if (Object.keys(body).sort().join(",") !== "email,password" || body.email !== "admin@example.com" || body.password !== "senha interna válida 🔐") {
      return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401);
    }
    const token = `usiar_s1.${randomUUID()}.${randomBytes(32).toString("base64url")}`;
    const csrf = randomBytes(32).toString("base64url");
    internalSessions.set(token, { csrf, permission, active: true });
    const now = Date.now();
    return json(res, { token_type: "Bearer", session_token: token, csrf_token: csrf,
      idle_expires_at: new Date(now + 30 * 60_000).toISOString(), absolute_expires_at: new Date(now + 8 * 60 * 60_000).toISOString() }, 201);
  }
  if (req.url === "/api/v1/auth/session" && req.method === "DELETE") {
    if (scenario === "logout-unavailable") return json(res, { error: { code: "AUTHENTICATION_UNAVAILABLE" } }, 503);
    const token = req.headers.authorization?.replace(/^Bearer /, "");
    const session = internalSessions.get(token);
    if (!session) return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401);
    if (req.headers["x-csrf-token"] !== session.csrf) return json(res, { error: { code: "FORBIDDEN" } }, 403);
    session.active = false; res.writeHead(204, { "Cache-Control": "no-store" }); return res.end();
  }
  const authenticate = async () => {
    if (req.headers.cookie) throw new Error("browser cookie forwarded");
    const token = req.headers.authorization?.replace(/^Bearer /, "");
    if (token?.startsWith("usiar_s1.")) {
      const session = internalSessions.get(token);
      if (!session?.active) throw new Error("invalid internal session");
      return session.permission.split(" ").includes("dashboard:read");
    }
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
    if (url.searchParams.get("profile_id") !== usiarV2 || url.searchParams.has("profile_code")) return json(res, { error: { code: "VALIDATION_ERROR" } }, 422);
    const from = url.searchParams.get("from_datetime"); const to = url.searchParams.get("to_datetime");
    const empty = scenario === "empty";
    const zeroSnapshot = { processes_total: 0, current_candidate: 0, current_pending: 0, current_discarded: 0, needs_review: 0, selected: 0, human_pending: 0, human_discarded: 0, stale_reviews: 0, documents_total: 0, documents_with_artifact: 0, documents_with_text: 0 };
    const zeroActivity = { records_collected: 0, processes_first_seen: 0, documents_discovered: 0, document_screenings_total: 0, operational_resolutions_total: 0, human_reviews_total: 0, rounds_total: 0, rounds_success: 0, rounds_partial: 0, rounds_failed: 0 };
    const zeroFunnel = { records_collected: 0, unique_processes: 0, initial_candidate: 0, initial_pending: 0, initial_discarded: 0, document_evaluated: 0, operational_candidate: 0, operational_pending: 0, operational_discarded: 0, selected: 0, human_pending: 0, human_discarded: 0 };
    return json(res, {
      profile_id: usiarV2, period: { from_datetime: from, to_datetime: to },
      current_snapshot: empty ? zeroSnapshot : { ...zeroSnapshot, processes_total: 1, current_candidate: 1, needs_review: 1, documents_total: 2, documents_with_artifact: 1, documents_with_text: 1 },
      period_activity: empty ? zeroActivity : { ...zeroActivity, records_collected: 7, processes_first_seen: 1, documents_discovered: 2, document_screenings_total: 1, operational_resolutions_total: 1, rounds_total: 2, rounds_success: 1, rounds_partial: 1 },
      funnel: empty ? zeroFunnel : { ...zeroFunnel, records_collected: 7, unique_processes: 1, initial_candidate: 1, document_evaluated: 1, operational_candidate: 1 },
      source_coverage: empty ? [] : [{ source: "FONTE-NOVA", rounds: 2, successful_rounds: 1, partial_rounds: 1, failed_rounds: 0, records_collected: 7, unique_processes: 1 }],
    });
  }
  if (url.pathname === "/api/v1/opportunities") {
    if (scenario === "opportunities-expired") return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401);
    try {
      if (!await authenticate()) return json(res, { error: { code: "FORBIDDEN" } }, 403);
    } catch { return json(res, { error: { code: "INVALID_CREDENTIALS" } }, 401); }
    if (scenario === "opportunities-error") return json(res, { error: { code: "TEST_SECRET", message: "test-access-marker internal" } }, 503);
    if (scenario === "slow-opportunities") await new Promise(resolve => setTimeout(resolve, 750));
    const states = url.searchParams.getAll("operational_state");
    const validStates = states.length > 0 && states.every(value => ["CANDIDATE", "PENDING"].includes(value));
    if (url.searchParams.get("profile_id") !== usiarV2 || url.searchParams.has("profile_code") || !validStates ||
      url.searchParams.get("page_size") !== "25" || url.searchParams.get("sort") !== "publication_at" ||
      url.searchParams.get("direction") !== "DESC") return json(res, { error: { code: "VALIDATION_ERROR" } }, 422);
    const page = Number(url.searchParams.get("page"));
    const opportunity = (suffix, state, overrides = {}) => ({
      process_id: `c7d2d8d1-6dc4-4d2e-9aa5-ce4359ff9a${suffix}`,
      source: "PNCP", official_id: `PNCP-2026-${suffix}`, rhs_id: null,
      description_preview: state === "CANDIDATE" ? "Manutenção preventiva de sistemas de climatização" : "Manutenção e instalação de ar-condicionado para avaliação",
      organization_name: state === "CANDIDATE" ? "Universidade Pública" : "Hospital Municipal",
      organization_cnpj: null, municipality_name: state === "CANDIDATE" ? "Campinas" : "Santos", uf: "SP",
      modality: "Pregão Eletrônico", estimated_value: state === "CANDIDATE" ? "1234.56" : "0", monthly_value: null,
      publication_at: state === "CANDIDATE" ? "2026-10-13T09:45:00-03:00" : null,
      proposal_deadline_at: null, official_url: state === "CANDIDATE" ? "https://pncp.gov.br/app/editais/exemplo" : null,
      notice_number: state === "CANDIDATE" ? "EDITAL-42/2026" : null, operational_resolution_id: null,
      operational_state: state, operational_reason: state === "CANDIDATE" ? "INCLUDED_MAINTENANCE" : "MIXED_SCOPE_REVIEW",
      operational_resolved_at: null, human_review_status: "UNREVIEWED", human_decision: null, human_reason: null,
      reviewed_at: null, documents_count: 0, has_text: false, has_document_screening: false, latest_capture_at: null,
      ...overrides,
    });
    if (scenario === "empty") return json(res, { items: [], pagination: { page, page_size: 25, total_items: 0, total_pages: 0 } });
    const available = [opportunity("d4", "CANDIDATE"), opportunity("d5", "PENDING")].filter(item => states.includes(item.operational_state));
    const items = page === 1 ? available : states.length === 2 && page === 2 ? [opportunity("d6", "CANDIDATE", { organization_name: "Instituto Federal" })] : [];
    const total = states.length === 2 ? 26 : available.length;
    return json(res, { items, pagination: { page, page_size: 25, total_items: total, total_pages: Math.ceil(total / 25) } });
  }
  return json(res, {}, 404);
});
provider.listen(4443, "127.0.0.1");
api.listen(8100, "127.0.0.1");
const shutdown = () => {
  provider.close(); api.close();
  provider.closeAllConnections(); api.closeAllConnections();
  process.exit(0);
};
process.on("SIGTERM", shutdown); process.on("SIGINT", shutdown);
