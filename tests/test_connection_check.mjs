import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const original = readFileSync(new URL("./fixtures/jarvis_comet_v6.ts", import.meta.url), "utf8");
const candidate = readFileSync(new URL("../supabase/functions/jarvis-comet/index.ts", import.meta.url), "utf8");
assert.equal(createHash("sha256").update(original).digest("hex"),
  "00ae20b8e39d2550fe336a424794c57f45b6c2be13cb28618c6cd62e436fe40c");
const startMarker = "  // BEGIN ISOLATED CONNECTION CHECK\n";
const endMarker = "  // END ISOLATED CONNECTION CHECK\n\n";
const start = candidate.indexOf(startMarker);
const end = candidate.indexOf(endMarker, start) + endMarker.length;
assert.ok(start > 0 && end > start);
const corsLine = '"Access-Control-Allow-Headers": "Content-Type, Authorization, x-jarvis-key"';
assert.equal(candidate.split(corsLine).length, 2, "The CORS header change must occur exactly once");
assert.equal(candidate.split(startMarker).length, 2, "Only one connection-check block");
assert.equal(candidate.split(endMarker).length, 2, "Connection-check closure present");
assert.ok(candidate.includes('"Access-Control-Allow-Methods": "POST, OPTIONS"'));
assert.ok(!candidate.includes('url.searchParams.get("k")'));
assert.ok(candidate.includes("readDispatchGate(req)"));
// Defense in depth: GitHub Actions repository_dispatch must be independently gated.
const cloudWorkflow = readFileSync(new URL("../.github/workflows/jarvis-cloud.yml", import.meta.url), "utf8");
assert.ok(cloudWorkflow.includes("if: \u0024{{ github.event_name != 'repository_dispatch' || vars.JARVIS_REPOSITORY_DISPATCH_ENABLED == 'true' }}"),
  "Direct GitHub repository_dispatch must be blocked unless explicitly enabled");

function executable(source) {
  const erasures = [
    ['import "jsr:@supabase/functions-js/edge-runtime.d.ts";', ""],
    ["(req: Request): Promise<Response>", "(req)"],
    ["let body: unknown;", "let body;"],
    ["function backendAuthHeaders(): Record<string, string> | null", "function backendAuthHeaders()"],
    ["record as Record<string, string>", "record"],
    ["const record = body as Record<string, unknown>;", "const record = body;"],
    ['async function constantTimeEqual(expected: string, provided: string): Promise<boolean>', 'async function constantTimeEqual(expected, provided)'],
    ['async (s: string) =>', 'async (s) =>'],
    ['async function readDispatchGate(req: Request): Promise<"allowed" | "paused" | "unknown">', 'async function readDispatchGate(req)'],
    ['const rows: unknown', 'const rows'],
    ['rows[0] as Record<string, unknown>', 'rows[0]'],
    ["function json(body: unknown, status = 200, extraHeaders: Record<string, string> = {})",
      "function json(body, status = 200, extraHeaders = {})"],
    ["function htmlPage(title: string, body: string, extraHeaders: Record<string, string> = {})",
      "function htmlPage(title, body, extraHeaders = {})"],
    ["function escapeHtml(s: string): string", "function escapeHtml(s)"],
    ["}[c]!));", "}[c]));"],
  ];
  for (const [from, to] of erasures) {
    assert.equal(source.split(from).length, 2, `Unique TypeScript erasure: ${from}`);
    source = source.replace(from, to);
  }
  return source;
}

const KEY = "synthetic-endpoint-fixture";
const PAT = "synthetic-github-fixture";
const SERVICE = "synthetic-service-fixture";
const MARKER = "synthetic-sensitive-error-body";
const CHECK_ID = "cc62340c-98bc-409b-9a40-6523e1eade84";
const SUPABASE = "https://fzmnqvmfilqizzftphbt.supabase.co";
const DISPATCH = "https://api.github.com/repos/rickyraippalinna/jarvis-omega-v2/dispatches";
const GATE = `${SUPABASE}/rest/v1/system_config?key=eq.autonomy_enabled&select=value`;
const validBody = { action: "verify_connection", check_id: CHECK_ID };

async function exercise(source, fixture = {}) {
  let handler;
  const requests = [];
  const logs = [];
  const controller = new AbortController();
  if (fixture.aborted) controller.abort();
  class FixedDate extends Date {
    constructor(...args) { super(...(args.length ? args : ["2026-09-22T17:33:00Z"])); }
  }
  const env = {
    JARVIS_ENDPOINT_KEY: KEY,
    JARVIS_COMET_DISPATCH_ENABLED: "true",
    JARVIS_GITHUB_PAT: PAT,
    SUPABASE_URL: SUPABASE,
    SUPABASE_SERVICE_ROLE_KEY: SERVICE,
    SUPABASE_SECRET_KEY: "sb_secret_synthetic_fixture",
    ...(fixture.env ?? {}),
  };
  const context = vm.createContext({
    Request, Response, URL, URLSearchParams, AbortSignal, TextEncoder, atob, crypto: webcrypto, Date: FixedDate,
    Deno: { serve(value) { handler = value; }, env: { get(name) { return env[name]; } } },
    console: { info(...args) { logs.push(args); }, log(...args) { logs.push(args); } },
    async fetch(url, options) {
      requests.push({
        url, method: options.method, redirect: options.redirect,
        headers: { ...options.headers },
        body: options.body ? JSON.parse(options.body) : null,
      });
      // Local fixtures only. The real network is never used.
      if (url === GATE) {
        if (fixture.throwGate) throw new Error(MARKER);
        if (fixture.abortAfterGate) controller.abort();
        return new Response(fixture.gateBody ?? JSON.stringify([{ value: "true" }]), {
          status: fixture.gateStatus ?? 200,
        });
      }
      assert.equal(url, DISPATCH);
      if (fixture.throwDispatch) throw new Error(MARKER);
      const status = fixture.dispatchStatus ?? 204;
      return new Response(status === 204 ? null : MARKER, { status });
    },
  });
  new vm.Script(executable(source)).runInContext(context);
  const method = fixture.method ?? "POST";
  const headers = {
    "x-jarvis-key": KEY,
    "content-type": "application/json",
    ...(fixture.headers ?? {}),
  };
  for (const name of fixture.omitHeaders ?? []) delete headers[name];
  const init = { method, headers, signal: controller.signal };
  if (method === "POST") {
    init.body = typeof fixture.body === "string"
      ? fixture.body : JSON.stringify(fixture.body ?? validBody);
  }
  const response = await handler(new Request(
    `${SUPABASE}/functions/v1/jarvis-comet${fixture.query ?? ""}`, init,
  ));
  return {
    status: response.status,
    body: await response.text(),
    headers: Object.fromEntries(response.headers),
    requests,
    logs,
  };
}

const taskCases = [
  { name: "independent Comet kill switch missing", body: { q: "safe" }, env: { JARVIS_COMET_DISPATCH_ENABLED: "" }, status: 423, calls: 0 },
  { name: "independent Comet kill switch false", body: { q: "safe" }, env: { JARVIS_COMET_DISPATCH_ENABLED: "false" }, status: 423, calls: 0 },
  { name: "GET cannot start work", method: "GET", status: 405, calls: 0 },
  { name: "legacy URL key rejected", method: "GET", query: `?k=${KEY}`,
    omitHeaders: ["x-jarvis-key"], status: 400, calls: 0 },
  { name: "URL task blocked", method: "GET", query: "?q=run", status: 400, calls: 0 },
  { name: "missing task rejected", body: {}, status: 400, calls: 0 },
  { name: "missing auth rejected", omitHeaders: ["x-jarvis-key"], status: 401, calls: 0 },
  { name: "bad auth rejected", headers: { "x-jarvis-key": "bad" }, status: 401, calls: 0 },
  { name: "tenant forgery blocked", body: { q: "safe", tenant: "other" }, status: 400, calls: 0 },
  { name: "user forgery blocked", body: { q: "safe", user_id: "other" }, status: 400, calls: 0 },
  { name: "Notion destination blocked", body: { q: "safe", notion: "other" }, status: 400, calls: 0 },
  { name: "oversized task blocked", body: { q: "a".repeat(4100) }, status: 400, calls: 0 },
  { name: "invalid tier blocked", body: { q: "safe", tier: "ULTRA" }, status: 400, calls: 0 },
  { name: "autonomy off", body: { q: "safe" },
    gateBody: '[{"value":false}]', status: 423, calls: 1 },
  { name: "autonomy unreadable", body: { q: "safe" },
    gateStatus: 401, status: 503, calls: 1 },
  { name: "invalid database origin", body: { q: "safe" },
    env: { SUPABASE_URL: "https://wrong.invalid" }, status: 503, calls: 0 },
  { name: "normal dispatch rejected", body: { q: "safe" },
    dispatchStatus: 401, status: 502, calls: 2 },
];
for (const f of taskCases) {
  const v = await exercise(candidate, f);
  assert.equal(v.status, f.status, f.name);
  assert.equal(v.requests.length, f.calls, f.name);
  for (const secret of [KEY, PAT, SERVICE, MARKER]) {
    assert.ok(!v.body.includes(secret), f.name + ": no secret in response");
  }
  process.stdout.write(`PASS secure task: ${f.name}\n`);
}
for (const fmt of ["json", "html"]) {
  const v = await exercise(candidate, { body: { q: "approved synthetic task", fmt } });
  assert.equal(v.status, fmt === "json" ? 202 : 200);
  assert.equal(v.requests.length, 2);
  assert.equal(v.requests[0].url, GATE);
  assert.equal(v.requests[0].redirect, "error");
  assert.equal(v.requests[1].redirect, "error");
  assert.deepEqual(v.requests[1].body, {
    event_type: "jarvis-run",
    client_payload: {
      task: "[ricky] approved synthetic task", tier: "LOW",
      notion_page_id: "3ca66d43-c107-813b-90f3-daf5b5a42333",
      user_id: "ricky", tenant: "ricky",
    },
  });
  process.stdout.write(`PASS normal dispatch ${fmt}\n`);
}

const preflight = await exercise(candidate, {
  method: "OPTIONS",
  omitHeaders: ["x-jarvis-key"],
  headers: {
    "Origin": "https://www.perplexity.ai",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "x-jarvis-key,content-type",
  },
});
assert.equal(preflight.status, 200);
assert.match(preflight.headers["access-control-allow-headers"], /x-jarvis-key/i);
assert.deepEqual(preflight.requests, [], "Preflight must not read state or dispatch work");
assert.equal(preflight.body, "");
process.stdout.write("PASS browser header preflight without side effects\n");

const failureCases = [
  { name: "connection check blocked by independent Comet kill switch", env: { JARVIS_COMET_DISPATCH_ENABLED: "false" }, status: 423, calls: 0 },
  { name: "missing authentication", omitHeaders: ["x-jarvis-key"], status: 401, calls: 0 },
  { name: "wrong authentication", headers: { "x-jarvis-key": "wrong" }, status: 401, calls: 0 },
  { name: "unknown action", body: { ...validBody, action: "typo" }, status: 400, calls: 0 },
  { name: "empty check ID", body: { ...validBody, check_id: "" }, status: 400, calls: 0 },
  { name: "trailing newline excluded", body: { ...validBody, check_id: CHECK_ID + "\n" },
    status: 400, calls: 0 },
  { name: "unsafe check ID", body: { ...validBody, check_id: "$(fixture)" }, status: 400, calls: 0 },
  { name: "task injection excluded", body: { ...validBody, q: MARKER }, status: 400, calls: 0 },
  { name: "alternate task excluded", body: { ...validBody, task: MARKER }, status: 400, calls: 0 },
  { name: "Notion destination excluded", body: { ...validBody, notion: MARKER }, status: 400, calls: 0 },
  { name: "tier override excluded", body: { ...validBody, tier: "HIGH" }, status: 400, calls: 0 },
  { name: "query arguments excluded", query: "?q=fixture", status: 400, calls: 0 },
  { name: "query credential excluded", query: `?k=${KEY}`, status: 400, calls: 0 },
  { name: "GET action rejected", method: "GET",
    query: `?action=verify_connection&check_id=${CHECK_ID}`, status: 400, calls: 0 },
  { name: "form action rejected", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: `action=verify_connection&check_id=${CHECK_ID}`, status: 415, calls: 0 },
  { name: "aborted before start", aborted: true, status: 499, calls: 0 },
  { name: "wrong database host", env: { SUPABASE_URL: "https://not-authorized.invalid" },
    status: 503, calls: 0 },
  { name: "missing database credential", env: { SUPABASE_SERVICE_ROLE_KEY: "", SUPABASE_SECRET_KEY: "" },
    status: 503, calls: 0 },
  { name: "anon legacy credential rejected", env: { SUPABASE_SERVICE_ROLE_KEY: "not-a-service-jwt", SUPABASE_SECRET_KEY: "" }, status: 503, calls: 0 },
  { name: "missing dispatch credential", env: { JARVIS_GITHUB_PAT: "" },
    status: 503, calls: 0 },
  { name: "kill switch false", gateBody: '[{"value":false}]', status: 423, calls: 1 },
  { name: "kill switch string false", gateBody: '[{"value":"false"}]', status: 423, calls: 1 },
  { name: "kill switch missing", gateBody: "[]", status: 503, calls: 1 },
  { name: "kill switch null", gateBody: '[{"value":null}]', status: 503, calls: 1 },
  { name: "kill switch ambiguous", gateBody: '[{"value":"true"},{"value":"true"}]',
    status: 503, calls: 1 },
  { name: "kill switch malformed JSON", gateBody: MARKER, status: 503, calls: 1 },
  { name: "kill switch unreadable", gateStatus: 403, status: 503, calls: 1 },
  { name: "kill switch transport failure", throwGate: true, status: 503, calls: 1 },
  { name: "cancelled before dispatch", abortAfterGate: true, status: 499, calls: 1 },
  { name: "GitHub rejects token", dispatchStatus: 401, status: 502, calls: 2 },
  { name: "GitHub response must be exact", dispatchStatus: 200, status: 502, calls: 2 },
  { name: "dispatch failure never retries", throwDispatch: true, status: 503, calls: 2 },
];
for (const fixture of failureCases) {
  const result = await exercise(candidate, fixture);
  assert.equal(result.status, fixture.status, fixture.name);
  assert.equal(result.requests.length, fixture.calls, fixture.name);
  assert.deepEqual(result.logs, [], fixture.name);
  for (const secret of [KEY, PAT, SERVICE, MARKER]) {
    assert.ok(!result.body.includes(secret), `No sensitive output: ${fixture.name}`);
  }
  assert.ok(!JSON.stringify(result.requests.map((r) => r.body)).includes('"jarvis-run"'));
  process.stdout.write(`PASS fail closed: ${fixture.name}\n`);
}

for (const value of ["true", true]) {
  const result = await exercise(candidate, { gateBody: JSON.stringify([{ value }]) });
  assert.equal(result.status, 202);
  assert.equal(result.headers["cache-control"], "no-store");
  assert.deepEqual(result.logs, []);
  assert.equal(result.requests.length, 2);
  const [gate, dispatch] = result.requests;
  assert.equal(gate.url, GATE);
  assert.equal(gate.method, "GET");
  assert.equal(gate.headers.Authorization, undefined);
  assert.equal(gate.headers.apikey, "sb_secret_synthetic_fixture");
  assert.equal(dispatch.url, DISPATCH);
  assert.equal(dispatch.method, "POST");
  assert.equal(dispatch.headers.Authorization, `Bearer ${PAT}`);
  assert.equal(gate.redirect, "error");
  assert.equal(dispatch.redirect, "error");
  assert.deepEqual(dispatch.body, {
    event_type: "jarvis-connection-check",
    client_payload: { check_id: CHECK_ID },
  });
  assert.deepEqual(JSON.parse(result.body), {
    ok: true, check_id: CHECK_ID, dispatch_accepted: true,
    connection_check_only: true, inference_requested: false,
    status_url: "https://github.com/rickyraippalinna/jarvis-omega-v2/actions/workflows/jarvis-connection-check.yml",
  });
  for (const secret of [KEY, PAT, SERVICE]) assert.ok(!result.body.includes(secret));
  process.stdout.write(`PASS isolated dispatch with autonomy ${JSON.stringify(value)}\n`);
}
process.stdout.write(JSON.stringify({
  status: "tested_locally_not_deployed",
  fixture_count: taskCases.length + failureCases.length + 5,
  network_requests: 0,
  original_source_sha256: createHash("sha256").update(original).digest("hex"),
  candidate_source_sha256: createHash("sha256").update(candidate).digest("hex"),
}) + "\n");
