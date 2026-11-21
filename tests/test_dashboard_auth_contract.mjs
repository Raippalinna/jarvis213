// Offline-only contract test: no live Deno network or credentials.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const code = readFileSync(new URL("../supabase/functions/jarvis-dashboard-api/index.ts", import.meta.url), "utf8");
const start = code.indexOf("function sb() {");
const end = code.indexOf("  return {", start);
assert.ok(start >= 0 && end > start, "backend header builder not found");
const sbSnippet = (code.slice(start, end) + "  return { url, headers };\n}")
  .replace("let url: string;", "let url;")
  .replace("const headers: Record<string, string>", "const headers");
assert.ok(!sbSnippet.includes("Record<string"), "unexpected TS annotation");

function headersFor(config) {
  const context = {
    URL,
    Deno: { env: { get: (k) => config[k] } },
    EXPECTED_SUPABASE_ORIGIN: "https://fzmnqvmfilqizzftphbt.supabase.co",
  };
  vm.createContext(context);
  vm.runInContext(sbSnippet + "; globalThis.getHeaders = sb;", context);
  return context.getHeaders();
}

const url = "https://fzmnqvmfilqizzftphbt.supabase.co";

test("modern secret key: only apikey, never Authorization: Bearer", () => {
  const { headers, url: origin } = headersFor({
    SUPABASE_URL: url,
    SUPABASE_SECRET_KEY: "sb_secret_test_value",
    SUPABASE_SERVICE_ROLE_KEY: "legacy.jwt.signature",
  });
  assert.equal(origin, url);
  assert.equal(headers.apikey, "sb_secret_test_value");
  assert.equal(headers.Authorization, undefined);
});

test("legacy service_role fallback remains backwards-compatible", () => {
  const { headers } = headersFor({
    SUPABASE_URL: url,
    SUPABASE_SERVICE_ROLE_KEY: "legacy.jwt.signature",
  });
  assert.equal(headers.apikey, "legacy.jwt.signature");
  assert.equal(headers.Authorization, "Bearer legacy.jwt.signature");
});

test("unknown, public, or missing credentials fail closed", () => {
  for (const configuration of [
    { SUPABASE_URL: url, SUPABASE_SECRET_KEY: "sb_publishable_no" },
    { SUPABASE_URL: url, SUPABASE_SECRET_KEY: "unknown" },
    { SUPABASE_URL: url, SUPABASE_SERVICE_ROLE_KEY: "sb_publishable_test" },
    { SUPABASE_URL: url },
  ]) assert.throws(() => headersFor(configuration));
});

test("backend key is never sent to an unrelated origin", () => {
  for (const invalidUrl of [
    "https://example.org", "http://fzmnqvmfilqizzftphbt.supabase.co",
    "https://fzmnqvmfilqizzftphbt.supabase.co.evil.test",
    "https://fzmnqvmfilqizzftphbt.supabase.co/other",
    "https://fzmnqvmfilqizzftphbt.supabase.co?redirect=1",
    "https://u:p@fzmnqvmfilqizzftphbt.supabase.co",
  ]) assert.throws(() => headersFor({ SUPABASE_URL: invalidUrl, SUPABASE_SECRET_KEY: "sb_secret_test" }));
});

test("dashboard authentication only accepts header, never URL query key", async () => {
  const section = code.match(/async function authorize\(req: Request\): Promise<boolean> \{[\s\S]*?\n\}/);
  assert.ok(section, "header-only authorize function missing");
  const js = section[0].replace("req: Request", "req").replace(": Promise<boolean>", "").replaceAll(".get<Json[]>", ".get");
  const context = {
    Deno: { env: { get: (k) => k === "JARVIS_ENDPOINT_KEY" ? "synthetic-dashboard-key" : "" } },
    sb: () => ({ get: async () => [] }),
    sha256Hex: async () => "",
  };
  vm.createContext(context);
  vm.runInContext(js + "; globalThis.check = authorize;", context);
  const header = (v) => ({ headers: { get: (k) => k === "x-jarvis-key" ? v : null } });
  assert.equal(await context.check(header("synthetic-dashboard-key")), true);
  assert.equal(await context.check(header(null)), false);
  assert.ok(!section[0].includes("searchParams"), "query-based credentials must be rejected");
  assert.ok(!code.includes("authorize(req, url)"), "URL must not reach the auth function");
});
