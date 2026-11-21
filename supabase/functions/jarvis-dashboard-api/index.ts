// JARVIS Dashboard API - edge function för Rickys Jarvis-dashboard (webb + mobil)
//
// Auth: header `x-jarvis-key` (eller ?k=) måste matcha JARVIS_ENDPOINT_KEY (Supabase secret)
//       ELLER SHA-256 av värdet matcha system_config.dashboard_password_sha256 (valfritt).
// Läsning sker med SUPABASE_SERVICE_ROLE_KEY server-side; ingen nyckel lämnar funktionen.
//
// Endpoints (POST JSON eller GET ?action=):
//   action=state                      -> KPI, initiativ, system, connector-hälsa, händelser, minne
//   action=chat_send {message,tier}   -> skapar jarvis_chat-rad och dispatchar JARVIS Prime (GitHub)
//                                        eller svarar direkt om LLM_API_KEY finns (mode=instant)
//   action=chat_get {id}              -> status/svar för en fråga
//   action=chat_list {limit}          -> senaste frågorna
//   action=health                     -> {ok, autonomy, has_llm} utan hemligheter
//
// Skrivningar: endast jarvis_chat (egen tabell) + GitHub repository_dispatch (befintligt flöde).
// Respekterar system_config.autonomy_enabled: false/okänt => ingen dispatch.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const GITHUB_OWNER = "rickyraippalinna";
const GITHUB_REPO = "jarvis-omega-v2";
const NOTION_LOG_PAGE_ID = "3ca66d43-c107-813b-90f3-daf5b5a42333";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-jarvis-key",
  "Cache-Control": "no-store",
};

type Json = Record<string, unknown>;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors },
  });
}

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sb() {
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!url || !key) throw new Error("Supabase-konfiguration saknas");
  const headers = {
    apikey: key,
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  return {
    async get<T = Json[]>(path: string): Promise<T> {
      const r = await fetch(`${url}/rest/v1/${path}`, { headers, signal: AbortSignal.timeout(8000) });
      if (!r.ok) throw new Error(`REST ${path.split("?")[0]} ${r.status}`);
      return await r.json();
    },
    async insert<T = Json[]>(table: string, row: Json): Promise<T> {
      const r = await fetch(`${url}/rest/v1/${table}`, {
        method: "POST",
        headers: { ...headers, Prefer: "return=representation" },
        body: JSON.stringify(row),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) throw new Error(`INSERT ${table} ${r.status}`);
      return await r.json();
    },
    async patch(table: string, filter: string, row: Json): Promise<void> {
      const r = await fetch(`${url}/rest/v1/${table}?${filter}`, {
        method: "PATCH",
        headers: { ...headers, Prefer: "return=minimal" },
        body: JSON.stringify(row),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) throw new Error(`PATCH ${table} ${r.status}`);
    },
  };
}

async function authorize(req: Request, url: URL): Promise<boolean> {
  const provided = (req.headers.get("x-jarvis-key") ?? url.searchParams.get("k") ?? "").trim();
  if (!provided) return false;
  const expected = Deno.env.get("JARVIS_ENDPOINT_KEY") ?? "";
  if (expected && provided === expected) return true;
  try {
    const rows = await sb().get<Json[]>("system_config?key=eq.dashboard_password_sha256&select=value");
    const hash = rows?.[0]?.value;
    if (typeof hash === "string" && hash.length === 64) {
      return (await sha256Hex(provided)) === hash.toLowerCase();
    }
  } catch { /* faller igenom till false */ }
  return false;
}

async function readAutonomy(): Promise<boolean | null> {
  try {
    const rows = await sb().get<Json[]>("system_config?key=eq.autonomy_enabled&select=value");
    const v = rows?.[0]?.value;
    if (v === true || v === "true") return true;
    if (v === false || v === "false") return false;
  } catch { /* okänt */ }
  return null;
}

async function getState(): Promise<Json> {
  const db = sb();
  const since24h = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const [config, dashboard, episodes, events, health, chats, approvals, memoryCount] = await Promise.allSettled([
    db.get("system_config?select=key,value,updated_at&order=key"),
    db.get("jarvis_dashboard_v2?select=category,initiative_name,initiative_status,initiative_owner,next_step,next_step_deadline,kpi_type,kpi_value,kpi_unit,kpi_target,system_name,system_status,system_last_check,updated_at&order=category,initiative_name,kpi_type,system_name"),
    db.get("memory_episode?select=episode_type,title,summary,started_at,source_systems&order=started_at.desc&limit=12"),
    db.get(`event?select=event_type,source,classification,occurred_at&occurred_at=gte.${since24h}&order=occurred_at.desc&limit=50`),
    db.get("connector_health?select=connector,status,latency_ms,scopes_ok,e2e_verified,checked_at&order=checked_at.desc&limit=60"),
    db.get("jarvis_chat?select=id,question,answer,status,tier,mode,provider,model,quality,cost_sek,latency_ms,run_url,error,created_at,answered_at&order=created_at.desc&limit=20"),
    db.get("approval_request?select=id,request_type,risk_class,requested_at,response&response=is.null&order=requested_at.desc&limit=10"),
    db.get("jarvis_memory?select=id&limit=1000"),
  ]);
  const val = <T>(r: PromiseSettledResult<T>, fallback: T): T => r.status === "fulfilled" ? r.value : fallback;

  // Senaste hälsorad per connector
  const latestHealth: Record<string, Json> = {};
  for (const h of val(health, [] as Json[])) {
    const c = String(h.connector);
    if (!latestHealth[c]) latestHealth[c] = h;
  }
  const dash = val(dashboard, [] as Json[]);
  const eventsList = val(events, [] as Json[]);
  const byType: Record<string, number> = {};
  for (const e of eventsList) byType[String(e.event_type)] = (byType[String(e.event_type)] ?? 0) + 1;

  return {
    generated_at: new Date().toISOString(),
    autonomy: await readAutonomy(),
    config: val(config, []),
    initiatives: dash.filter((d) => d.category === "initiative"),
    kpis: dash.filter((d) => d.category === "kpi"),
    systems: dash.filter((d) => d.category === "system"),
    episodes: val(episodes, []),
    events: { last24h: eventsList.length, by_type: byType, latest: eventsList.slice(0, 15) },
    connector_health: Object.values(latestHealth),
    chats: val(chats, []),
    approvals_pending: val(approvals, []),
    memory_chunks: (val(memoryCount, [] as Json[])).length,
    has_llm: Boolean(Deno.env.get("LLM_API_KEY")),
    errors: [config, dashboard, episodes, events, health, chats, approvals, memoryCount]
      .filter((r) => r.status === "rejected")
      .map((r) => String((r as PromiseRejectedResult).reason?.message ?? "fel")),
  };
}

async function instantAnswer(message: string, history: Array<{ role: string; content: string }>): Promise<Json> {
  const apiKey = Deno.env.get("LLM_API_KEY") ?? "";
  const baseUrl = (Deno.env.get("LLM_BASE_URL") ?? "https://api.perplexity.ai").replace(/\/$/, "");
  const model = Deno.env.get("LLM_MODEL") ?? "sonar-pro";
  const system = [
    "Du är JARVIS, RICKY Ω∞ OS: Ricky Raippalinnas strategiska hjärna och operativa genomförare.",
    "Svara på svenska, slutsats först, direkt och konkret. Skilj verifierat faktum, beräkning, antagande och förslag.",
    "Hitta aldrig på siffror, källor eller genomförda åtgärder. Lova aldrig rikedom eller säker avkastning.",
    "Du svarar i dashboard-läget 'instant'; för långa uppdrag föreslå att Ricky skickar frågan till JARVIS Prime (tier LOW/MED/HIGH).",
  ].join(" ");
  const t0 = Date.now();
  const r = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages: [{ role: "system", content: system }, ...history.slice(-8), { role: "user", content: message }],
      max_tokens: 1200,
      temperature: 0.3,
    }),
    signal: AbortSignal.timeout(40000),
  });
  if (!r.ok) throw new Error(`LLM ${r.status}`);
  const d = await r.json();
  return {
    answer: d.choices?.[0]?.message?.content ?? "",
    model: d.model ?? model,
    latency_ms: Date.now() - t0,
    citations: d.citations ?? [],
  };
}

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  if (!(await authorize(req, url))) return json({ error: "Unauthorized" }, 401);

  let body: Json = {};
  if (req.method === "POST") body = await req.json().catch(() => ({}));
  const action = String(body.action ?? url.searchParams.get("action") ?? "state");

  try {
    if (action === "health") {
      return json({ ok: true, autonomy: await readAutonomy(), has_llm: Boolean(Deno.env.get("LLM_API_KEY")), time: new Date().toISOString() });
    }
    if (action === "state") return json(await getState());

    if (action === "chat_list") {
      const limit = Math.min(Number(body.limit ?? 30), 100);
      return json({ chats: await sb().get(`jarvis_chat?select=*&order=created_at.desc&limit=${limit}`) });
    }
    if (action === "chat_get") {
      const id = String(body.id ?? url.searchParams.get("id") ?? "");
      if (!/^[0-9a-f-]{36}$/.test(id)) return json({ error: "ogiltigt id" }, 400);
      const rows = await sb().get<Json[]>(`jarvis_chat?select=*&id=eq.${id}`);
      return rows?.[0] ? json(rows[0]) : json({ error: "not found" }, 404);
    }

    if (action === "chat_send") {
      const message = String(body.message ?? "").trim();
      const tier = String(body.tier ?? "LOW").toUpperCase();
      const wantMode = String(body.mode ?? "auto");
      if (!message) return json({ error: "message saknas" }, 400);
      if (message.length > 4000) return json({ error: "message för långt (max 4000)" }, 400);
      if (!/^(FREE|LOW|MED|HIGH)$/.test(tier)) return json({ error: "tier måste vara FREE, LOW, MED eller HIGH" }, 400);

      const db = sb();
      const useInstant = (wantMode === "instant" || wantMode === "auto") && Boolean(Deno.env.get("LLM_API_KEY"));

      if (useInstant) {
        const [row] = await db.insert<Json[]>("jarvis_chat", { question: message, tier, mode: "instant", status: "running", started_at: new Date().toISOString() });
        try {
          const history = Array.isArray(body.history) ? body.history as Array<{ role: string; content: string }> : [];
          const a = await instantAnswer(message, history);
          await db.patch("jarvis_chat", `id=eq.${row.id}`, { status: "answered", answer: a.answer, model: a.model, provider: "instant", latency_ms: a.latency_ms, answered_at: new Date().toISOString() });
          return json({ id: row.id, mode: "instant", status: "answered", answer: a.answer, model: a.model, latency_ms: a.latency_ms, citations: a.citations });
        } catch (e) {
          await db.patch("jarvis_chat", `id=eq.${row.id}`, { status: "failed", error: String((e as Error).message).slice(0, 200), answered_at: new Date().toISOString() });
          if (wantMode === "instant") return json({ id: row.id, mode: "instant", status: "failed", error: "Instant-svar misslyckades" }, 502);
          // auto: fall igenom till Prime
        }
      }

      // JARVIS Prime via GitHub Actions
      const autonomy = await readAutonomy();
      if (autonomy !== true) {
        return json({ error: autonomy === false ? "Autonomi är pausad (system_config.autonomy_enabled=false)" : "Autonomistatus okänd – ingen dispatch" }, 423);
      }
      const pat = Deno.env.get("JARVIS_GITHUB_PAT") ?? "";
      if (!pat) return json({ error: "JARVIS_GITHUB_PAT saknas" }, 503);

      const [row] = await db.insert<Json[]>("jarvis_chat", { question: message, tier, mode: "prime", status: "queued" });
      const dispatch = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dispatches`, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${pat}`,
          "Content-Type": "application/json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "jarvis-dashboard-api",
        },
        body: JSON.stringify({
          event_type: "jarvis-run",
          client_payload: { task: `[ricky] ${message}`, tier, notion_page_id: NOTION_LOG_PAGE_ID, user_id: "ricky", tenant: "ricky", chat_id: row.id },
        }),
        signal: AbortSignal.timeout(10000),
      });
      if (dispatch.status !== 204) {
        await db.patch("jarvis_chat", `id=eq.${row.id}`, { status: "failed", error: `GitHub dispatch ${dispatch.status}` });
        return json({ id: row.id, mode: "prime", status: "failed", error: "GitHub dispatch avvisades" }, 502);
      }
      return json({
        id: row.id, mode: "prime", status: "queued", eta_seconds: 60,
        status_url: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/jarvis-cloud.yml`,
      }, 202);
    }

    return json({ error: `okänd action: ${action}` }, 400);
  } catch (e) {
    return json({ error: String((e as Error).message ?? "fel").slice(0, 200) }, 500);
  }
});
