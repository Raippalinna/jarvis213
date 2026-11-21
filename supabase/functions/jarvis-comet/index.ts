// JARVIS Comet Endpoint - global edge function
//
// Anrop: POST /functions/v1/jarvis-comet med JSON-body {task,tier,fmt}.
// Credential: endast x-jarvis-key i header. URL-nycklar avvisas.
//
// Autentisering: endpoint_key jämförs mot JARVIS_ENDPOINT_KEY (Supabase secret).
// GitHub PAT lagras som JARVIS_GITHUB_PAT (Supabase secret) och används för
// repository_dispatch mot rickyraippalinna/jarvis-omega-v2.
//
// Privat owner-endpoint: tenant och Notion-mål är serverstyrda.
// Klientens user_id/tenant/notion är inte verifierade identiteter och accepteras inte.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const GITHUB_OWNER = "rickyraippalinna";
const GITHUB_REPO = "jarvis-omega-v2";
const NOTION_LOG_PAGE_ID = "3ca66d43-c107-813b-90f3-daf5b5a42333";

const EXPECTED_SUPABASE_ORIGIN = "https://fzmnqvmfilqizzftphbt.supabase.co";

// Kompatibel backendauktorisering för både sb_secret_ och signerad
// legacy service_role JWT. Nyckelns faktiska typ styr headern.
// Ingen credential skickas till främmande origin eller till klienten.
function backendCredential() {
  const url = (Deno.env.get("SUPABASE_URL") ?? "").trim();
  const preferred = (Deno.env.get("SUPABASE_SECRET_KEY") ?? "").trim();
  const legacy = (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "").trim();
  const key = preferred || legacy;
  if (url !== EXPECTED_SUPABASE_ORIGIN || !key) return null;
  const isModern = key.startsWith("sb_secret_");
  if (preferred && !isModern) return null;
  if (!isModern) {
    const parts = key.split(".");
    if (parts.length !== 3) return null;
    try {
      const raw = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      const padded = raw.padEnd(Math.ceil(raw.length / 4) * 4, "=");
      const role = JSON.parse(atob(padded)).role;
      if (role !== "service_role") return null;
    } catch {
      return null;
    }
  }
  const headers = { "apikey": key, "Accept": "application/json" };
  if (!isModern) Object.assign(headers, { "Authorization": `Bearer ${key}` });
  return { url, headers };
}

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);

  // CORS för Comet-browser eller vilken klient som helst
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, x-jarvis-key",
  };
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  // Autentisering - jämför endpoint_key
  const providedKey = req.headers.get("x-jarvis-key") ?? "";
  const expectedKey = Deno.env.get("JARVIS_ENDPOINT_KEY") ?? "";
  if (url.searchParams.has("k") || !expectedKey || providedKey !== expectedKey) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json", ...cors },
    });
  }

  // Parsa parametrar (stöd både GET query och POST body)
  let params: URLSearchParams;
  if (req.method === "POST") {
    const ct = req.headers.get("content-type") ?? "";
    if (ct.includes("application/json")) {
      const body = await req.json().catch(() => ({}));
      params = new URLSearchParams(body as Record<string, string>);
    } else {
      params = new URLSearchParams(await req.text());
    }
  } else {
    params = url.searchParams;
  }

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

    const backend = backendCredential();
    const githubPat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
    if (!backend || !githubPat) {
      return json({ error: "Connection-check configuration unavailable" }, 503, checkHeaders);
    }

    try {
      const signal = AbortSignal.any([req.signal, AbortSignal.timeout(10000)]);
      const gate = await fetch(
        `${backend.url}/rest/v1/system_config?key=eq.autonomy_enabled&select=value`,
        { method: "GET", redirect: "error", signal, headers: backend.headers },
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

  // Säkert normalflöde. Connection-check ovan är isolerad och oförändrad.
  if (req.method !== "POST") {
    return json({ error: "POST required" }, 405, cors);
  }
  if (url.search !== "") {
    return json({ error: "URL parameters are not accepted" }, 400, cors);
  }
  if ((req.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase() !== "application/json") {
    return json({ error: "application/json required" }, 415, cors);
  }
  const allowed = new Set(["task", "q", "tier", "fmt"]);
  if ([...params.keys()].some((key) => !allowed.has(key)) ||
      [...params.keys()].some((key) => params.getAll(key).length !== 1)) {
    return json({ error: "Unsupported request parameter" }, 400, cors);
  }

  const task = (params.get("task") ?? params.get("q") ?? "").trim();
  const tier = (params.get("tier") ?? "LOW").toUpperCase();
  const format = params.get("fmt") ?? "json";
  if (!task || task.length > 4000 || /[\u0000-\u001F]/.test(task)) {
    return json({ error: "Invalid task (1–4000 characters)" }, 400, cors);
  }
  if (!/^(FREE|LOW|MED|HIGH)$/.test(tier)) {
    return json({ error: "Invalid tier" }, 400, cors);
  }
  if (format !== "json" && format !== "html") {
    return json({ error: "Invalid format" }, 400, cors);
  }

  const backend = backendCredential();
  if (!backend) {
    return json({ error: "Autonomy verification unavailable" }, 503, cors);
  }
  const signal = AbortSignal.any([req.signal, AbortSignal.timeout(10000)]);

  try {
    // False, absent, unreadable or malformed autonomy state => no normal dispatch.
    const gate = await fetch(
      `${backend.url}/rest/v1/system_config?key=eq.autonomy_enabled&select=value`,
      { method: "GET", headers: backend.headers, redirect: "error", signal },
    );
    if (!gate.ok) return json({ error: "Autonomy verification unavailable" }, 503, cors);
    const rows = await gate.json();
    if (!Array.isArray(rows) || rows.length !== 1 ||
        !rows[0] || typeof rows[0] !== "object") {
      return json({ error: "Autonomy verification unavailable" }, 503, cors);
    }
    const state = rows[0].value;
    if (state === false || state === "false") {
      return json({ error: "Autonomy is paused" }, 423, cors);
    }
    if (state !== true && state !== "true") {
      return json({ error: "Autonomy verification unavailable" }, 503, cors);
    }

    const githubPat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
    if (!githubPat) return json({ error: "Dispatch unavailable" }, 503, cors);
    if (req.signal.aborted) return json({ error: "Request cancelled" }, 499, cors);

    const tenant = "ricky";
    const dispatchRes = await fetch(
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`,
      {
        method: "POST", redirect: "error", signal,
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
            task: `[ricky] ${task}`,
            tier,
            notion_page_id: NOTION_LOG_PAGE_ID,
            user_id: "ricky",
            tenant,
            origin_claim: "comet",
          },
        }),
      },
    );
    // GitHub repository_dispatch succeeds only with 204. Never return upstream error bodies.
    if (dispatchRes.status !== 204) {
      return json({ error: "GitHub dispatch rejected" }, 502, cors);
    }
    const actionsUrl = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions`;
    const notionUrl = `https://app.notion.com/p/${NOTION_LOG_PAGE_ID.replace(/-/g, "")}`;
    if (format === "json") {
      return json({
        ok: true, status: "queued", task, tier, tenant,
        dispatched_at: new Date().toISOString(),
        status_url: actionsUrl, result_url: notionUrl,
      }, 202, { ...cors, "Cache-Control": "no-store" });
    }
    return htmlPage(
      `Jarvis uppdrag mottaget (${tier})`,
      `<p><strong>Uppdrag:</strong> ${escapeHtml(task)}</p>
       <p>Se <a href="${actionsUrl}">GitHub Actions</a> eller
       <a href="${notionUrl}">Notion Control Room</a> för resultat.</p>`,
      { ...cors, "Cache-Control": "no-store" },
      202,
    );
  } catch {
    return json({ error: req.signal.aborted ? "Request cancelled" : "Dispatch unavailable" },
      req.signal.aborted ? 499 : 503, cors);
  }
});

function json(body: unknown, status = 200, extraHeaders: Record<string, string> = {}) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}

function htmlPage(title: string, body: string, extraHeaders: Record<string, string> = {}, status = 200) {
  const html = `<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:640px;margin:2rem auto;padding:1rem;line-height:1.5;color:#222}
h1{font-size:1.4rem;margin:0 0 1rem}form{display:flex;flex-direction:column;gap:.6rem}
input,select,button{padding:.5rem;font-size:1rem;border:1px solid #ccc;border-radius:4px}
button{background:#111;color:#fff;cursor:pointer;font-weight:600}a{color:#0057ff}</style>
</head><body><h1>${escapeHtml(title)}</h1>${body}</body></html>`;
  return new Response(html, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8", ...extraHeaders },
  });
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>\"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]!));
}
