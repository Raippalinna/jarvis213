// JARVIS Comet Endpoint - global edge function
//
// Anrop: GET/POST /functions/v1/jarvis-comet?k=<endpoint_key>&q=<fråga>&tier=<FREE|LOW|MED|HIGH>
//
// Autentisering: endpoint_key jämförs mot JARVIS_ENDPOINT_KEY (Supabase secret).
// GitHub PAT lagras som JARVIS_GITHUB_PAT (Supabase secret) och används för
// repository_dispatch mot rickyraippalinna/jarvis-omega-v2.
//
// Multi-tenant-förberedelse: user_id och tenant hämtas från query, injiceras
// i client_payload så Jarvis-workflow kan skriva scoped chunks till pgvector.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const GITHUB_OWNER = "rickyraippalinna";
const GITHUB_REPO = "jarvis-omega-v2";
const NOTION_LOG_PAGE_ID = "3ca66d43-c107-813b-90f3-daf5b5a42333";

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);

  // CORS för Comet-browser eller vilken klient som helst
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  // Autentisering - jämför endpoint_key
  const providedKey = url.searchParams.get("k") ?? req.headers.get("x-jarvis-key") ?? "";
  const expectedKey = Deno.env.get("JARVIS_ENDPOINT_KEY") ?? "";
  if (!expectedKey || providedKey !== expectedKey) {
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

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const githubPat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
    if (
      supabaseUrl !== "https://fzmnqvmfilqizzftphbt.supabase.co" ||
      !serviceKey || !githubPat
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
          headers: {
            "Accept": "application/json",
            "apikey": serviceKey,
            "Authorization": `Bearer ${serviceKey}`,
          },
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

  const task = (params.get("q") ?? params.get("task") ?? "").trim();
  const tier = (params.get("tier") ?? "LOW").toUpperCase();
  const tenant = params.get("tenant") ?? "ricky";
  const userId = params.get("user_id") ?? tenant;
  const notionPageId = params.get("notion") ?? NOTION_LOG_PAGE_ID;
  const format = params.get("fmt") ?? "html";

  if (!task) {
    return htmlPage(
      "Ge en fråga",
      `<form method="GET">
        <input type="hidden" name="k" value="${escapeHtml(providedKey)}" />
        <label>Fråga: <input type="text" name="q" size="60" autofocus /></label>
        <label>Tier: <select name="tier"><option>LOW</option><option>MED</option><option>HIGH</option><option>FREE</option></select></label>
        <button type="submit">Kör Jarvis</button>
      </form>`,
      cors,
    );
  }

  if (!/^(FREE|LOW|MED|HIGH)$/.test(tier)) {
    return json({ error: "tier måste vara FREE, LOW, MED eller HIGH" }, 400, cors);
  }

  // Trigga GitHub repository_dispatch
  const githubPat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
  if (!githubPat) {
    return json({ error: "JARVIS_GITHUB_PAT saknas som secret" }, 500, cors);
  }

  const dispatchRes = await fetch(
    `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`,
    {
      method: "POST",
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

  if (!dispatchRes.ok) {
    const body = await dispatchRes.text();
    return json({
      error: "GitHub dispatch failed",
      status: dispatchRes.status,
      body: body.slice(0, 300),
    }, 502, cors);
  }

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
      eta_seconds: 40,
    }, 200, cors);
  }

  // Default: HTML-svar som visas i Comet
  return htmlPage(
    `🤖 Jarvis kör (${tier})`,
    `<p><strong>Fråga:</strong> ${escapeHtml(task)}</p>
     <p><strong>Tenant:</strong> ${escapeHtml(tenant)} · <strong>Tier:</strong> ${tier}</p>
     <p>Svaret postas automatiskt till <a href="${notionUrl}" target="_blank">Notion Control Room</a> inom ~40 sekunder.</p>
     <p><a href="${actionsUrl}" target="_blank">Se live-status</a></p>
     <p style="color:#888;font-size:0.9em">Anropad ${new Date().toISOString()}</p>`,
    cors,
  );
});

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
