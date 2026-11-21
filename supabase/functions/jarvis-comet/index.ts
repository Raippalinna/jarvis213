// JARVIS Comet Endpoint - global edge function
//
// Anrop: POST JSON med x-jarvis-key. Ingen autentisering via URL.
//
// Autentisering: endpoint_key jämförs mot JARVIS_ENDPOINT_KEY (Supabase secret).
// GitHub PAT lagras som JARVIS_GITHUB_PAT (Supabase secret) och används för
// repository_dispatch mot rickyraippalinna/jarvis-omega-v2.
//
// Enskild tenant och Notion-destination låses server-side, aldrig från anropsdata.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const GITHUB_OWNER = "rickyraippalinna";
const GITHUB_REPO = "jarvis-omega-v2";
const NOTION_LOG_PAGE_ID = "3ca66d43-c107-813b-90f3-daf5b5a42333";

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);

  // CORS för Comet-browser eller vilken klient som helst
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, x-jarvis-key",
  };
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  // URL credentials or query dispatches must never execute.
  if (url.search) return json({ error: "Query parameters are not accepted" }, 400, cors);
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405, cors);
  const expectedKey = Deno.env.get("JARVIS_ENDPOINT_KEY") ?? "";
  const providedKey = req.headers.get("x-jarvis-key") ?? "";
  if (!expectedKey || providedKey.length > 512 ||
      !(await constantTimeEqual(expectedKey, providedKey))) {
    return json({ error: "Unauthorized" }, 401, cors);
  }

  if ((req.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase() !== "application/json") {
    return json({ error: "Expected JSON" }, 415, cors);
  }
  const raw = await req.text().catch(() => "");
  if (!raw || new TextEncoder().encode(raw).length > 8192) {
    return json({ error: "Invalid request size" }, 413, cors);
  }
  let body: unknown;
  try { body = JSON.parse(raw); }
  catch { return json({ error: "Invalid JSON" }, 400, cors); }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return json({ error: "Invalid request body" }, 400, cors);
  }
  const record = body as Record<string, unknown>;
  if (Object.values(record).some((value) => typeof value !== "string")) {
    return json({ error: "Invalid request fields" }, 400, cors);
  }
  // Connection-check retains its previously reviewed, isolated contract.
  const params = new URLSearchParams(record as Record<string, string>);

  // BEGIN ISOLATED CONNECTION CHECK
  // This reserved action never enters the normal task/model/Notion route.
  if (params.has("action")) {
    const checkHeaders = { ...cors, "Cache-Control": "no-store" };
    const checkId = params.get("check_id") ?? "";
    const keys = Array.from(params.keys());
    const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
    if (
      params.get("action") !== "verify_connection" ||
      req.method !== "POST" || url.search !== "" ||
      req.headers.get("x-jarvis-key") !== expectedKey ||
      (req.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase() !== "application/json" ||
      keys.length !== 2 || !keys.includes("action") || !keys.includes("check_id") ||
      checkId.length !== 36 || !uuidV4.test(checkId)
    ) {
      return json({ error: "Invalid connection-check request" }, 400, checkHeaders);
    }
    if (req.signal.aborted) {
      return json({ error: "Connection check cancelled" }, 499, checkHeaders);
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const backendHeaders = backendAuthHeaders();
    const githubPat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
    if (
      supabaseUrl !== "https://fzmnqvmfilqizzftphbt.supabase.co" ||
      !backendHeaders || !githubPat
    ) {
      return json({ error: "Connection-check configuration unavailable" }, 503, checkHeaders);
    }

    try {
      const signal = AbortSignal.any([req.signal, AbortSignal.timeout(10000)]);
      const gate = await fetch(
        `${supabaseUrl}/rest/v1/system_config?key=eq.autonomy_enabled&select=value`,
        {
          method: "GET",
          redirect: "error",
          signal,
          headers: backendHeaders,
        },
      );
      if (!gate.ok) {
        return json({ error: "Autonomy state unavailable" }, 503, checkHeaders);
      }
      const rows = await gate.json();
      if (!Array.isArray(rows) || rows.length !== 1 || !rows[0] || typeof rows[0] !== "object") {
        return json({ error: "Autonomy state unavailable" }, 503, checkHeaders);
      }
      const autonomy = rows[0].value;
      if (autonomy === false || autonomy === "false") {
        return json({ error: "Autonomy is paused" }, 423, checkHeaders);
      }
      if (autonomy !== true && autonomy !== "true") {
        return json({ error: "Autonomy state unavailable" }, 503, checkHeaders);
      }
      if (req.signal.aborted) {
        return json({ error: "Connection check cancelled" }, 499, checkHeaders);
      }

      const dispatch = await fetch(
        `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`,
        {
          method: "POST",
          redirect: "error",
          signal,
          headers: {
            "Accept": "application/vnd.github+json",
            "Authorization": `Bearer ${githubPat}`,
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jarvis-comet-connection-check",
          },
          body: JSON.stringify({
            event_type: "jarvis-connection-check",
            client_payload: { check_id: checkId },
          }),
        },
      );
      if (dispatch.status !== 204) {
        return json({ error: "Connection-check dispatch rejected", status: dispatch.status }, 502, checkHeaders);
      }
      return json({
        ok: true,
        check_id: checkId,
        dispatch_accepted: true,
        connection_check_only: true,
        inference_requested: false,
        status_url: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/jarvis-connection-check.yml`,
      }, 202, checkHeaders);
    } catch {
      // Do not echo upstream bodies, URLs, secrets, or raw exception messages.
      // No automatic retry: a timed-out dispatch may already have been accepted.
      return json({
        error: req.signal.aborted ? "Connection check cancelled" : "Connection check failed",
      }, req.signal.aborted ? 499 : 503, checkHeaders);
    }
  }
  // END ISOLATED CONNECTION CHECK

  // No caller-supplied identity, Notion destination or arbitrary actions.
  const allowed = new Set(["q", "task", "tier", "fmt"]);
  if (Array.from(params.keys()).some((key) => !allowed.has(key)) ||
      (params.has("q") && params.has("task"))) {
    return json({ error: "Unsupported request fields" }, 400, cors);
  }
  const task = (params.get("q") ?? params.get("task") ?? "").trim();
  const tier = (params.get("tier") ?? "LOW").toUpperCase();
  const format = params.get("fmt") ?? "json";
  const tenant = "ricky";
  const userId = "ricky";
  const notionPageId = NOTION_LOG_PAGE_ID;
  if (!task || task.length > 4000 ||
      /[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F]/.test(task)) {
    return json({ error: "Invalid task" }, 400, cors);
  }
  if (!/^(FREE|LOW|MED|HIGH)$/.test(tier) || !["json", "html"].includes(format)) {
    return json({ error: "Invalid tier or format" }, 400, cors);
  }
  if (req.signal.aborted) return json({ error: "Request cancelled" }, 499, cors);

  // A missing/disabled/unreadable autonomy gate fails closed.
  const gateResult = await readDispatchGate(req);
  if (gateResult !== "allowed") {
    return json({ error: gateResult === "paused" ? "Autonomy is paused" : "Autonomy unavailable" },
      gateResult === "paused" ? 423 : 503, cors);
  }
  const githubPat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
  if (!githubPat) return json({ error: "Dispatch unavailable" }, 503, cors);
  if (req.signal.aborted) return json({ error: "Request cancelled" }, 499, cors);

  let dispatched = false;
  try {
    const dispatchRes = await fetch(
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        redirect: "error",
        signal: AbortSignal.any([req.signal, AbortSignal.timeout(10000)]),
        headers: {
          "Accept": "application/vnd.github+json",
          "Authorization": `Bearer ${githubPat}`,
          "Content-Type": "application/json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "jarvis-comet-edge",
        },
        body: JSON.stringify({
          event_type: "jarvis-run",
          client_payload: {
            task: `[${tenant}] ${task}`,
            tier,
            notion_page_id: notionPageId,
            user_id: userId,
            tenant,
          },
        }),
      },
    );
    dispatched = dispatchRes.status === 204;
  } catch {
    // Never expose transport errors; a timed-out dispatch may have succeeded.
    return json({ error: "Dispatch outcome unknown; check GitHub Actions before retrying" }, 503, cors);
  }
  if (!dispatched) return json({ error: "Dispatch rejected" }, 502, cors);

  const actionsUrl = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions`;
  const notionUrl = `https://app.notion.com/p/${notionPageId.replace(/-/g, "")}`;

  if (format === "json") {
    return json({
      ok: true,
      task,
      tier,
      tenant,
      dispatched_at: new Date().toISOString(),
      status_url: actionsUrl,
      result_url: notionUrl,
    }, 202, cors);
  }

  // Default: HTML-svar som visas i Comet
  return htmlPage(
    `🤖 Jarvis kör (${tier})`,
    `<p><strong>Fråga:</strong> ${escapeHtml(task)}</p>
     <p><strong>Tenant:</strong> ${escapeHtml(tenant)} · <strong>Tier:</strong> ${tier}</p>
     <p>Körbegäran accepterad. Följ GitHub Actions för faktisk status. Planerad Notion-destination: <a href="${notionUrl}" target="_blank" rel="noopener noreferrer">Control Room</a>.</p>
     <p><a href="${actionsUrl}" target="_blank">Se live-status</a></p>
     <p style="color:#888;font-size:0.9em">Anropad ${new Date().toISOString()}</p>`,
    cors,
  );
});

async function constantTimeEqual(expected: string, provided: string): Promise<boolean> {
  const digest = async (s: string) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  const [a, b] = await Promise.all([digest(expected), digest(provided)]);
  let mismatch = a.length ^ b.length;
  for (let i = 0; i < a.length; i++) mismatch |= a[i] ^ (b[i] ?? 0);
  return mismatch === 0;
}

function backendAuthHeaders(): Record<string, string> | null {
  const modern = Deno.env.get("SUPABASE_SECRET_KEY") ?? "";
  if (modern) {
    if (!/^sb_secret_[A-Za-z0-9_-]{12,}$/.test(modern)) return null;
    return { Accept: "application/json", apikey: modern };
  }
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  try {
    const segment = legacy.split(".")[1] ?? "";
    const payload = JSON.parse(atob(segment.replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.role !== "service_role") return null;
  } catch { return null; }
  return { Accept: "application/json", apikey: legacy, Authorization: `Bearer ${legacy}` };
}

async function readDispatchGate(req: Request): Promise<"allowed" | "paused" | "unknown"> {
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  if (url !== "https://fzmnqvmfilqizzftphbt.supabase.co") return "unknown";
  const headers = backendAuthHeaders();
  if (!headers) return "unknown";
  try {
    const res = await fetch(`${url}/rest/v1/system_config?key=eq.autonomy_enabled&select=value`, {
      method: "GET",
      redirect: "error",
      signal: AbortSignal.any([req.signal, AbortSignal.timeout(8000)]),
      headers,
    });
    if (!res.ok) return "unknown";
    const rows: unknown = await res.json();
    if (!Array.isArray(rows) || rows.length !== 1 || !rows[0] || typeof rows[0] !== "object") return "unknown";
    const value = (rows[0] as Record<string, unknown>).value;
    if (value === true || value === "true") return "allowed";
    if (value === false || value === "false") return "paused";
  } catch { /* No upstream error data leaves the function. */ }
  return "unknown";
}

function json(body: unknown, status = 200, extraHeaders: Record<string, string> = {}) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}

function htmlPage(title: string, body: string, extraHeaders: Record<string, string> = {}) {
  const html = `<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:640px;margin:2rem auto;padding:1rem;line-height:1.5;color:#222}
h1{font-size:1.4rem;margin:0 0 1rem}form{display:flex;flex-direction:column;gap:.6rem}
input,select,button{padding:.5rem;font-size:1rem;border:1px solid #ccc;border-radius:4px}
button{background:#111;color:#fff;cursor:pointer;font-weight:600}a{color:#0057ff}</style>
</head><body><h1>${escapeHtml(title)}</h1>${body}</body></html>`;
  return new Response(html, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8", ...extraHeaders },
  });
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>\"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]!));
}
