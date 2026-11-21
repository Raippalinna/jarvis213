import assert from "node:assert/strict";
import { createHash } from "node:crypto";
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
assert.equal(candidate.slice(0, start) + candidate.slice(end), original,
  "Only the isolated connection-check block may differ from production v6");

function executable(source) {
  const erasures = [
    ['import "jsr:@supabase/functions-js/edge-runtime.d.ts";', ""],
    ["(req: Request): Promise<Response>", "(req)"],
    ["let params: URLSearchParams;", "let params;"],
    ["body as Record<string, string>", "body"],
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
    JARVIS_GITHUB_PAT: PAT,
    SUPABASE_URL: SUPABASE,
    SUPABASE_SERVICE_ROLE_KEY: SERVICE,
    ...(fixture.env ?? {}),
  };
  const context = vm.createContext({
    Request, Response, URL, URLSearchParams, AbortSignal, Date: FixedDate,
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

const legacyCases = [
  { name: "unauthenticated GET", method: "GET", omitHeaders: ["x-jarvis-key"] },
  { name: "authenticated GET without task", method: "GET" },
  { name: "wrong key", method: "GET", headers: { "x-jarvis-key": "incorrect" } },
  { name: "missing configured key", method: "GET", env: { JARVIS_ENDPOINT_KEY: "" } },
  { name: "legacy query authentication", method: "GET", query: `?k=${KEY}`,
    omitHeaders: ["x-jarvis-key"] },
  { name: "OPTIONS", method: "OPTIONS", omitHeaders: ["x-jarvis-key"] },
  { name: "HEAD", method: "HEAD" },
  { name: "empty POST", body: {} },
  { name: "malformed POST", body: "{" },
  { name: "legacy invalid tier", body: { q: "fixture", tier: "INVALID", fmt: "json" } },
  { name: "legacy missing PAT", body: { q: "fixture", fmt: "json" },
    env: { JARVIS_GITHUB_PAT: "" } },
  { name: "legacy task dispatch stub", body: { q: "fixture", fmt: "json" } },
  { name: "legacy GET task stub", method: "GET", query: "?q=fixture&fmt=json" },
];
for (const fixture of legacyCases) {
  assert.deepEqual(await exercise(candidate, fixture), await exercise(original, fixture),
    fixture.name);
  process.stdout.write(`PASS unchanged: ${fixture.name}\n`);
}

const failureCases = [
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
    body: `action=verify_connection&check_id=${CHECK_ID}`, status: 400, calls: 0 },
  { name: "aborted before start", aborted: true, status: 499, calls: 0 },
  { name: "wrong database host", env: { SUPABASE_URL: "https://not-authorized.invalid" },
    status: 503, calls: 0 },
  { name: "missing database credential", env: { SUPABASE_SERVICE_ROLE_KEY: "" },
    status: 503, calls: 0 },
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
  assert.equal(gate.headers.Authorization, `Bearer ${SERVICE}`);
  assert.equal(gate.headers.apikey, SERVICE);
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
  fixture_count: legacyCases.length + failureCases.length + 2,
  network_requests: 0,
  original_source_sha256: createHash("sha256").update(original).digest("hex"),
  candidate_source_sha256: createHash("sha256").update(candidate).digest("hex"),
}) + "\n");
