import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

// Execute the actual Edge JavaScript (subset of TypeScript) with mocked network.
const file = readFileSync(new URL("../supabase/functions/jarvis-approval-admin/index.ts", import.meta.url), "utf8");
const source = file.replace('import "jsr:@supabase/functions-js/edge-runtime.d.ts";', "");
assert.notEqual(source, file);
const USER = "58a5b2f3-51d4-481a-9a2c-74dedb63a9e1";
const OTHER = "c4a85f0a-414b-4c8b-a258-97f15f2775f1";
const TENANT = "00000000-0000-0000-0000-000000000001";
const PRINCIPAL = "22222222-2222-2222-2222-222222222222";
const REQUEST_ID = "16dd4ea1-891a-47a2-9aa5-7d83be88bbd2";
const DECISION_ID = "1da2a5c5-72f7-43a5-a9bd-676ee7c744f1";
const BASE = "https://fzmnqvmfilqizzftphbt.supabase.co";

async function exercise(opts = {}) {
  const requests = [];
  let handler;
  const env = {
    SUPABASE_URL: BASE,
    SUPABASE_SECRET_KEY: "sb_secret_synthetic",
    SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic",
    JARVIS_APPROVAL_ALLOWED_ORIGINS: "https://dashboard.example.test",
    ...(opts.env || {}),
  };
  const fakeFetch = async (url, config) => {
    requests.push({ url: String(url), method: config.method, body: config.body });
    if (String(url).endsWith("/auth/v1/user")) {
      return Response.json(opts.invalidToken ? { error: "invalid" } : { id: USER },
        { status: opts.invalidToken ? 401 : 200 });
    }
    if (String(url).includes("jarvis_approval_admin?")) {
      return Response.json(opts.noAdmin ? [] : [{ tenant_id: TENANT, principal_id: PRINCIPAL }]);
    }
    if (String(url).includes("approval_decision?")) {
      return Response.json([{ id: DECISION_ID, title: "Synthetic review", draft_ref: "sha256:" + "a".repeat(64) }]);
    }
    if (String(url).includes("approval_request?")) {
      return Response.json([{ id: REQUEST_ID, decision_id: DECISION_ID, risk_class: "R2", expires_at: "2099-01-01Z" }]);
    }
    if (String(url).endsWith("/rpc/jarvis_approval_decide")) {
      if (opts.rejectRpc) return Response.json({ secret: "do not leak" }, { status: 409 });
      return Response.json({ request_id: REQUEST_ID, response: "approved" });
    }
    throw new Error("unexpected URL " + url);
  };
  vm.runInNewContext(source, {
    Deno: { env: { get: (name) => env[name] ?? "" }, serve: (fn) => { handler = fn; } },
    URL, Response, Request, AbortSignal, TextDecoder, Uint8Array, atob, Date, Set, Map, fetch: fakeFetch,
  }, { timeout: 1000 });
  const headers = { ...(opts.headers ?? {}) };
  if (opts.auth !== false) headers.authorization = "Bearer synthetic.access.valid.jwt";
  const req = new Request(BASE + "/functions/v1/jarvis-approval-admin" + (opts.query ?? ""), {
    method: opts.method ?? "POST", headers,
    ...(opts.method === "GET" || opts.method === "OPTIONS" ? {} : {
      body: opts.rawBody ?? JSON.stringify(opts.body ?? { action: "list" }),
    }),
  });
  const result = await handler(req);
  return { status: result.status, body: result.status === 204 ? null : await result.json(), requests };
}

test("unknown browser Origin cannot use endpoint", async () => {
  const r = await exercise({ headers: { origin: "https://attacker.test" } });
  assert.equal(r.status, 403);
  assert.equal(r.requests.length, 0);
});

test("missing, rejected or malformed JWT fails closed", async () => {
  assert.equal((await exercise({ auth: false })).status, 401);
  assert.equal((await exercise({ invalidToken: true })).status, 401);
});

test("signed-in user without owner admin mapping is not enough", async () => {
  const r = await exercise({ noAdmin: true });
  assert.equal(r.status, 403);
  assert.equal(r.requests.length, 2);
});

test("GET and query credentials are rejected without authorization lookups", async () => {
  for (const x of [{ method: "GET" }, { query: "?k=unsafe" }]) {
    const r = await exercise(x);
    assert.equal(r.status, 405);
    assert.equal(r.requests.length, 0);
  }
});

test("list reads only from membership-resolved tenant, not requester input", async () => {
  const r = await exercise({ body: { action: "list", tenant_id: OTHER } });
  assert.equal(r.status, 200);
  assert.equal(r.body.pending[0].request_id, REQUEST_ID);
  const listUrl = r.requests.find((x) => x.url.includes("approval_decision?")).url;
  assert.ok(listUrl.includes("tenant_id=eq." + TENANT));
  assert.equal(listUrl.includes(OTHER), false);
});

test("approval RPC actor is verified Auth identity, never user-supplied", async () => {
  const r = await exercise({
    headers: { origin: "https://dashboard.example.test" },
    body: { action: "decide", request_id: REQUEST_ID, decision: "approved", p_auth_user_id: OTHER },
  });
  assert.equal(r.status, 200);
  const call = r.requests.find((x) => x.url.includes("/rpc/jarvis_approval_decide"));
  assert.ok(call);
  assert.equal(JSON.parse(call.body).p_auth_user_id, USER);
  assert.equal(JSON.parse(call.body).p_request_id, REQUEST_ID);
});

test("invalid decision never reaches atomic approval RPC", async () => {
  const r = await exercise({ body: { action: "decide", request_id: "not-a-uuid", decision: "approved" } });
  assert.equal(r.status, 400);
  assert.equal(r.requests.some((x) => x.url.includes("rpc/jarvis_approval_decide")), false);
});

test("failed RPC is opaque; no backend message leaks", async () => {
  const r = await exercise({
    body: { action: "decide", request_id: REQUEST_ID, decision: "approved" },
    rejectRpc: true,
  });
  assert.equal(r.status, 503);
  assert.equal(JSON.stringify(r.body).includes("do not leak"), false);
});

test("OPTIONS CORS is restricted to configured origin", async () => {
  assert.equal((await exercise({ method: "OPTIONS", auth: false, headers: { origin: "https://dashboard.example.test" } })).status, 204);
  assert.equal((await exercise({ method: "OPTIONS", auth: false, headers: { origin: "https://attacker.test" } })).status, 403);
});

test("wrong Supabase project fails before any outgoing network", async () => {
  const r = await exercise({ env: { SUPABASE_URL: "https://malicious.example.test" } });
  assert.equal(r.status, 503);
  assert.equal(r.requests.length, 0);
});


test("oversized UTF-8 input is rejected by actual byte count, not JS string length", async () => {
  // The string has fewer than 4096 code points but exceeds 4096 UTF-8 bytes.
  const payload = JSON.stringify({ action: "list", padding: "ä".repeat(2300) });
  assert.ok(payload.length < 4096);
  assert.ok(Buffer.byteLength(payload, "utf8") > 4096);
  const r = await exercise({ rawBody: payload });
  assert.equal(r.status, 413);
  assert.equal(r.requests.some(x => x.url.includes("approval_decision?")), false);
});

test("invalid UTF-8 body fails closed before approval list or decision", async () => {
  const r = await exercise({ rawBody: Uint8Array.from([0xff, 0xfe, 0x00]) });
  assert.equal(r.status, 413);
  assert.equal(r.requests.some(x => x.url.includes("approval_decision?")), false);
});

test("Content-Length over cap is rejected before authorization lookup", async () => {
  const r = await exercise({ headers: { "content-length": "4097" } });
  assert.equal(r.status, 413);
  assert.equal(r.requests.length, 0);
});
