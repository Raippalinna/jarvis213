import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

// Isolerad, nyckelfri verifiering av just produktionsfunktionens autentiseringskod.
// Ingen Supabase-anslutning, GitHub-dispatch eller modellkörning görs.
const source = readFileSync(new URL("../supabase/functions/jarvis-dashboard-api/index.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("../apps/dashboard/src/api.ts", import.meta.url), "utf8");

function extract(start, end) {
  const i = source.indexOf(start);
  const j = source.indexOf(end, i);
  assert.ok(i >= 0 && j > i, `Saknar förväntad kod: ${start}`);
  return source.slice(i, j);
}

const hashing = extract("async function sha256Hex(", "\nfunction sb()")
  .replace("async function sha256Hex(s: string): Promise<string>", "async function sha256Hex(s)");
const authentication = extract("function constantTimeHexEqual(", "\nasync function readAutonomy")
  .replace("function constantTimeHexEqual(a: string, b: string): boolean", "function constantTimeHexEqual(a, b)")
  .replace("async function authorize(req: Request, url: URL): Promise<boolean>", "async function authorize(req, url)")
  .replace("sb().get<Json[]>", "sb().get");
const compiled = new vm.Script(`${hashing}\n${authentication}\nauthorize`);

async function verify({ key = "", endpoint = "generated-private-key", legacy = false,
  hash = "", query = "", readFails = false } = {}) {
  let databaseReads = 0;
  const env = { JARVIS_ENDPOINT_KEY: endpoint, JARVIS_ALLOW_LEGACY_PASSWORD: legacy ? "true" : "" };
  const context = vm.createContext({
    crypto: webcrypto,
    TextEncoder,
    Deno: { env: { get: (name) => env[name] ?? "" } },
    sb: () => ({ get: async () => {
      databaseReads++;
      if (readFails) throw new Error("synthetic database failure");
      return hash ? [{ value: hash }] : [];
    } }),
  });
  const authorize = compiled.runInContext(context);
  const req = { headers: { get: (name) => name === "x-jarvis-key" ? key : null } };
  const url = new URL("https://example.test/functions/v1/jarvis-dashboard-api" + query);
  const allowed = await authorize(req, url);
  return { allowed, databaseReads };
}

test("rätt endpointnyckel accepteras utan databasåtkomst", async () => {
  assert.deepEqual(await verify({ key: "generated-private-key" }), { allowed: true, databaseReads: 0 });
});

test("saknad, felaktig, tomkonfigurerad och blankstegsinbäddad nyckel avvisas", async () => {
  for (const input of [
    { key: "" }, { key: "wrong" },
    { key: "generated-private-key", endpoint: "" },
    { key: " generated-private-key" }, { key: "generated-private-key " },
  ]) {
    assert.equal((await verify(input)).allowed, false);
  }
});

test("URL-nyckel nekas även om en giltig header bifogas", async () => {
  assert.equal((await verify({ query: "?k=generated-private-key" })).allowed, false);
  assert.equal((await verify({ key: "generated-private-key", query: "?k=ignored" })).allowed, false);
});

test("legacy-SHA256 är avstängd som standard och ger inga DB-anrop", async () => {
  const hash = createHash("sha256").update("legacy-passphrase").digest("hex");
  assert.deepEqual(await verify({ key: "legacy-passphrase", hash }),
    { allowed: false, databaseReads: 0 });
});

test("legacy-migration kräver opt-in och korrekt SHA256-hash", async () => {
  const hash = createHash("sha256").update("legacy-passphrase").digest("hex");
  assert.deepEqual(await verify({ key: "legacy-passphrase", legacy: true, hash }),
    { allowed: true, databaseReads: 1 });
  assert.equal((await verify({ key: "incorrect", legacy: true, hash })).allowed, false);
  assert.equal((await verify({ key: "legacy-passphrase", legacy: true, hash: "invalid" })).allowed, false);
});

test("backendfel under legacy-kontroll leder till nekad åtkomst", async () => {
  assert.deepEqual(await verify({ key: "legacy-passphrase", legacy: true, readFails: true }),
    { allowed: false, databaseReads: 1 });
});

test("dashboarden hämtar bara uttryckligen tillåten systemkonfiguration", () => {
  assert.match(source, /system_config\?key=eq\.autonomy_enabled&select=key,value,updated_at/);
  assert.doesNotMatch(source, /system_config\?select=key,value,updated_at/);
  assert.match(source, /config: \(val\(config, \[\] as Json\[\]\)\)\.filter\(\(c\) => c\.key === "autonomy_enabled"\)/);
});

test("klienten läser inte längre känsliga nycklar från localStorage", () => {
  assert.doesNotMatch(client, /localStorage\.(?:getItem|setItem)\(KEY_STORAGE/);
  assert.match(client, /sessionStorage\.getItem\(KEY_STORAGE\)/);
  assert.match(client, /localStorage\.removeItem\(KEY_STORAGE\)/);
});
