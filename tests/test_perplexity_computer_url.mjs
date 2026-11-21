import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const moduleUrl = pathToFileURL(path.join(currentDir, "../apps/dashboard/src/perplexity-url.ts")).href;
const good = "https://www.perplexity.ai/computer/a/12345678-1234-4234-8234-1234567890ab";
const goodSession = "https://www.perplexity.ai/session/abcdef01-2345-4abc-8def-0123456789ab";
const goodTask = "https://www.perplexity.ai/computer/tasks/12345678-1234-4234-8234-1234567890ab";
const cases = [
  good,
  good.replace("www.perplexity.ai", "perplexity.ai"),
  goodSession,
  goodSession.replace("www.perplexity.ai", "perplexity.ai"),
  goodTask,
  goodTask.replace("www.perplexity.ai", "perplexity.ai"),
  "",
  "https://www.perplexity.ai.evil.test/computer/a/12345678-1234-4234-8234-1234567890ab",
  good.replace("https:", "http:"),
  good.replace("www.", "user:pass@www."),
  good.replace(".ai/", ".ai:8443/"),
  `${good}?secret=a`,
  `${good}#token`,
  "javascript:alert(1)",
  "https://www.perplexity.ai/computer/a/invalid",
  good.replace("/computer/a/", "/projects/"),
  `${goodSession}?secret=a`,
  `${goodSession}#token`,
  `${goodTask}?secret=a`,
  `${goodTask}#token`,
  goodTask.replace("/computer/tasks/", "/computer/task/"),
  goodTask.replace("/computer/tasks/", "/computer/tasks/extra/"),
  goodSession.replace("/session/", "/sessions/"),
  goodSession.replace("/session/", "/session/extra/"),
  goodSession.replace("/session/", "/session/%2e%2e/"),
  goodSession.replace("/session/", "/session/%2F"),
  `https://www.perplexity.ai\@evil.test/computer/a/12345678-1234-4234-8234-1234567890ab`,
];

function checkAll() {
  // Node 22's built-in TS stripper tests the actual production function, offline.
  const program = `import {validatePerplexityComputerLink} from ${JSON.stringify(moduleUrl)};\n` +
    "const cases=JSON.parse(process.env.JARVIS_CASES);process.stdout.write(JSON.stringify(cases.map(validatePerplexityComputerLink)));";
  const result = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", program], {
    encoding: "utf8", timeout: 5000,
    env: { PATH: process.env.PATH ?? "", JARVIS_CASES: JSON.stringify(cases) },
  });
  assert.equal(result.status, 0, `Code execution failed: ${result.stderr}`);
  return JSON.parse(result.stdout);
}

test("handoff accepts only canonical HTTPS Computer tasks, artifacts, and sessions", () => {
  const result = checkAll();
  assert.deepEqual(result[0], { ok: true, href: good });
  assert.deepEqual(result[1], { ok: true, href: good });
  assert.deepEqual(result[2], { ok: true, href: goodSession });
  assert.deepEqual(result[3], { ok: true, href: goodSession });
  assert.deepEqual(result[4], { ok: true, href: goodTask });
  assert.deepEqual(result[5], { ok: true, href: goodTask });
  for (const item of result.slice(6)) assert.equal(item.ok, false);
});

test("private URL is never included in a rejected-link error", () => {
  for (const outcome of checkAll().slice(6)) {
    assert.equal(typeof outcome.reason, "string");
    assert.ok(!outcome.reason.includes("12345678"));
    assert.ok(!outcome.reason.includes("abcdef01"));
  }
});
