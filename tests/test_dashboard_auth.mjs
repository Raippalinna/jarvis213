import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import vm from "node:vm";

// Kör enbart de verkliga auth-funktionerna isolerat med syntetiska nycklar.
// Inga serverhemligheter, nätverksanrop eller produktionsskrivningar behövs.
const source = readFileSync(
  new URL("../supabase/functions/jarvis-dashboard-api/index.ts", import.meta.url),
  "utf8",
);
const client = readFileSync(new URL("../apps/dashboard/src/api.ts", import.meta.url), "utf8");

function section(start, end) {
  const a = source.indexOf(start);
  const b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, "Hittade inte autentiseringsfunktionerna");
  return source.slice(a, b);
}
const authCode = [
  section("async function sha256Hex(", "function constantTimeHexEqual(")
    .replace("(s: string): Promise<string>", "(s)"),
  section("function constantTimeHexEqual(", "function sb()")
    .replace("(a: string, b: string): boolean", "(a, b)"),
  section("async function authorize(", "async function readAutonomy(")
    .replace("(req: Request, url: URL): Promise<boolean>", "(req, url)")
    .replace("sb().get<Json[]>", "sb().get"),
].join("\n");

async function check({ header, query = "", endpointKey = "synthetic-key",
  dbHash, failDb = false } = {}) {
  let dbReads = 0;
  const context = {
    crypto: webcrypto,
    Deno: { env: { get: (name) => name === "JARVIS_ENDPOINT_KEY" ? endpointKey : "" } },
    sb: () => ({ get: async () => {
      dbReads++;
      if (failDb) throw new Error("synthetic db failure");
      return dbHash === undefined ? [] : [{ value: dbHash }];
    } }),
    URL,
    Headers,
    TextEncoder,
  };
  vm.runInNewContext(authCode + "\nglobalThis.checkAuthorize = authorize;", context);
  const headers = new Headers(header === undefined ? {} : { "x-jarvis-key": header });
  const request = { headers };
  const url = new URL("https://example.invalid/functions/v1/jarvis-dashboard-api" + query);
  return { allowed: await context.checkAuthorize(request, url), dbReads };
}

test("godkänner rätt nyckel i header och behöver inte kontakta DB", async () => {
  assert.deepEqual(await check({ header: "synthetic-key" }), { allowed: true, dbReads: 0 });
});
test("avvisar saknad eller felaktig nyckel", async () => {
  assert.equal((await check()).allowed, false);
  assert.equal((await check({ header: "wrong" })).allowed, false);
  assert.equal((await check({ header: "" })).allowed, false);
});
test("avvisar alltid k i URL, även med korrekt header", async () => {
  assert.deepEqual(await check({ query: "?k=synthetic-key" }), { allowed: false, dbReads: 0 });
  assert.deepEqual(await check({ header: "synthetic-key", query: "?k=something" }), { allowed: false, dbReads: 0 });
  assert.deepEqual(await check({ header: "synthetic-key", query: "?k=" }), { allowed: false, dbReads: 0 });
});
test("accepterar legitimt SHA-256 fallback-lösenord och avvisar fel hash", async () => {
  const payload = new TextEncoder().encode("synthetic-password");
  const digest = await webcrypto.subtle.digest("SHA-256", payload);
  const hash = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, "0")).join("");
  assert.equal((await check({ header: "synthetic-password", endpointKey: "", dbHash: hash })).allowed, true);
  assert.equal((await check({ header: "wrong", endpointKey: "", dbHash: hash })).allowed, false);
  assert.equal((await check({ header: "synthetic-password", endpointKey: "", dbHash: "invalid" })).allowed, false);
});
test("stänger vid databasfel, för lång header eller saknade hemligheter", async () => {
  assert.equal((await check({ header: "fallback", endpointKey: "", failDb: true })).allowed, false);
  assert.deepEqual(await check({ header: "x".repeat(1025) }), { allowed: false, dbReads: 0 });
  assert.equal((await check({ header: "wrong", endpointKey: "" })).allowed, false);
});
test("klienten använder kortlivad fliklagring och skickar aldrig URL-nyckel", () => {
  assert.match(client, /sessionStorage\.getItem\(KEY_STORAGE\)/);
  assert.match(client, /sessionStorage\.setItem\(KEY_STORAGE, k\)/);
  assert.match(client, /localStorage\.removeItem\(KEY_STORAGE\)/);
  assert.doesNotMatch(client, /localStorage\.(getItem|setItem)\(/);
  assert.match(client, /"x-jarvis-key": getKey\(\)/);
});
