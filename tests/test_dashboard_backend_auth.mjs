import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

// Bara den verkliga Supabase-headerbyggaren körs med fiktiva nycklar.
// Nätverk, produktionsdata och GitHub-dispatch används inte.
const code = readFileSync(
  new URL("../supabase/functions/jarvis-dashboard-api/index.ts", import.meta.url), "utf8",
);
const start = code.indexOf("function sb() {");
const end = code.indexOf("  return {", start);
assert.ok(start >= 0 && end > start, "Supabase helper saknas");
const isolated = (code.slice(start, end) + "  return { url, headers };\n}")
  .replace("let url: string;", "let url;")
  .replace("const headers: Record<string, string>", "const headers");

function configure(env) {
  const context = vm.createContext({
    URL,
    atob,
    Deno: { env: { get: (name) => env[name] ?? "" } },
    EXPECTED_SUPABASE_ORIGIN: "https://fzmnqvmfilqizzftphbt.supabase.co",
  });
  const sb = new vm.Script(isolated + "\nsb").runInContext(context);
  return sb();
}

const correctUrl = "https://fzmnqvmfilqizzftphbt.supabase.co";

test("modern Supabase secret skickas bara i apikey, aldrig som Bearer", () => {
  const { url, headers } = configure({
    SUPABASE_URL: correctUrl,
    SUPABASE_SECRET_KEY: "sb_secret_test_value",
    SUPABASE_SERVICE_ROLE_KEY: "synthetic.jwt.fixture",
  });
  assert.equal(url, correctUrl);
  assert.equal(headers.apikey, "sb_secret_test_value");
  assert.equal(headers.Authorization, undefined);
});

test("modern sb_secret under legacy-variabel fungerar utan Bearer", () => {
  const { url, headers } = configure({
    SUPABASE_URL: correctUrl,
    SUPABASE_SERVICE_ROLE_KEY: "sb_secret_synthetic_legacy_env",
  });
  assert.equal(url, correctUrl);
  assert.equal(headers.apikey, "sb_secret_synthetic_legacy_env");
  assert.equal(headers.Authorization, undefined);
});

test("modern felaktigt format avvisas även med giltig legacy sb_secret", () => {
  assert.throws(() => configure({
    SUPABASE_URL: correctUrl,
    SUPABASE_SECRET_KEY: "sb_publishable_wrong_format",
    SUPABASE_SERVICE_ROLE_KEY: "sb_secret_synthetic_legacy_env",
  }));
});

test("legacy service_role används med Bearer när modern nyckel saknas", () => {
  // Enbart formell payload. Ingen verklig token/signatur används i tester.
  const legacy = "synthetic." +
    Buffer.from(JSON.stringify({ role: "service_role" })).toString("base64url") +
    ".signature";
  const { headers } = configure({
    SUPABASE_URL: correctUrl, SUPABASE_SERVICE_ROLE_KEY: legacy,
  });
  assert.equal(headers.apikey, legacy);
  assert.equal(headers.Authorization, "Bearer " + legacy);
});

test("legacy anon-JWT avvisas före nätverksanrop", () => {
  const anon = "synthetic." +
    Buffer.from(JSON.stringify({ role: "anon" })).toString("base64url") +
    ".signature";
  assert.throws(() => configure({
    SUPABASE_URL: correctUrl, SUPABASE_SERVICE_ROLE_KEY: anon,
  }));
});

test("fel typ och saknade backendnycklar avvisas före nätverksanrop", () => {
  for (const secrets of [
    {}, { SUPABASE_SECRET_KEY: "sb_publishable_no" },
    { SUPABASE_SECRET_KEY: "not-secret" },
    { SUPABASE_SERVICE_ROLE_KEY: "sb_publishable_test" },
    { SUPABASE_SERVICE_ROLE_KEY: "not-a-jwt" },
  ]) {
    assert.throws(() => configure({ SUPABASE_URL: correctUrl, ...secrets }));
  }
});

test("backendnyckeln kan inte skickas till fel origin eller via osäker URL", () => {
  const unsafeUrls = [
    "", "https://example.org", "http://fzmnqvmfilqizzftphbt.supabase.co",
    "https://fzmnqvmfilqizzftphbt.supabase.co.evil.invalid",
    "https://fzmnqvmfilqizzftphbt.supabase.co/rest/v1/",
    "https://fzmnqvmfilqizzftphbt.supabase.co?query=1",
    "https://user:pass@fzmnqvmfilqizzftphbt.supabase.co/",
    "https://fzmnqvmfilqizzftphbt.supabase.co/#fragment",
  ];
  for (const SUPABASE_URL of unsafeUrls) {
    assert.throws(() => configure({ SUPABASE_URL, SUPABASE_SECRET_KEY: "sb_secret_test" }),
      `origin/url must be rejected: ${SUPABASE_URL}`);
  }
});
