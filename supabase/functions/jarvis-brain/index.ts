// JARVIS Brain – read-only status endpoint with minimal public response.
// Public mode returns only a health marker. Private mode requires x-jarvis-key.
// Query-string authentication is deliberately rejected before any database access.
// No writes are performed; the service-role key is used only server-side in private mode.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ENDPOINT_KEY = Deno.env.get("JARVIS_ENDPOINT_KEY") ?? "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-jarvis-key",
  "Cache-Control": "no-store",
};

async function rest(path: string, signal: AbortSignal): Promise<{ rows: unknown[]; count: number | null }> {
  const r = await fetch(SUPABASE_URL + "/rest/v1/" + path, {
    signal,
    headers: {
      apikey: SERVICE_KEY,
      Authorization: "Bearer " + SERVICE_KEY,
      Prefer: "count=exact",
      Accept: "application/json",
    },
  });
  if (!r.ok) throw new Error(path.split("?")[0] + ": HTTP " + r.status);
  const cr = r.headers.get("content-range");
  const count = cr && cr.includes("/") && cr.split("/")[1] !== "*"
    ? Number(cr.split("/")[1])
    : null;
  return { rows: await r.json(), count };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...cors },
  });
}

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);

  // Do this before OPTIONS/auth/data access: no key or other parameter is accepted in a URL.
  if (url.search !== "") {
    return json({ error: "Query parameters are not accepted" }, 400);
  }

  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "GET" && req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  const providedKey = req.headers.get("x-jarvis-key") ?? "";
  const full = ENDPOINT_KEY !== "" && providedKey === ENDPOINT_KEY;
  if (providedKey && !full) return json({ error: "Unauthorized" }, 401);

  // Public mode does not touch Supabase and reveals no counters, event types or memory metadata.
  if (!full) {
    return json({
      ok: true,
      mode: "public",
      generated_at: new Date().toISOString(),
      read_only: true,
      status: "endpoint_only",
    });
  }

  if (!SUPABASE_URL || !SERVICE_KEY) {
    return json({ error: "Brain configuration unavailable" }, 503);
  }

  const signal = AbortSignal.timeout(9000);
  const out: Record<string, unknown> = {
    mode: "full",
    generated_at: new Date().toISOString(),
    read_only: true,
  };

  try {
    const [ev, ep, mem, ch, ap] = await Promise.all([
      rest("event?select=event_id&limit=1", signal),
      rest("memory_episode?select=id&limit=1", signal),
      rest("jarvis_memory?select=id&limit=1", signal),
      rest("connector_health?select=id&limit=1", signal),
      rest("approval_request?select=id&limit=1", signal),
    ]);
    out.counts = {
      event: ev.count,
      memory_episode: ep.count,
      jarvis_memory: mem.count,
      connector_health: ch.count,
      approval_request: ap.count,
    };

    const since = new Date(Date.now() - 14 * 864e5).toISOString();
    const evRows = (await rest(
      "event?select=occurred_at,event_type&occurred_at=gte." + since + "&order=occurred_at.desc&limit=2000",
      signal,
    )).rows as { occurred_at: string; event_type: string }[];
    const perDay: Record<string, number> = {};
    for (const e of evRows) {
      const d = (e.occurred_at || "").slice(0, 10);
      if (d) perDay[d] = (perDay[d] || 0) + 1;
    }
    out.events_per_day = Object.entries(perDay).sort().map(([d, n]) => ({ day: d, n }));

    const byType: Record<string, number> = {};
    for (const e of evRows) byType[e.event_type] = (byType[e.event_type] || 0) + 1;
    out.events_by_type_14d = byType;

    const memRows = (await rest(
      "jarvis_memory?select=source,kind,sensitivity&limit=5000",
      signal,
    )).rows as { source: string; kind: string; sensitivity: string }[];
    const bySource: Record<string, number> = {};
    for (const m of memRows) {
      const source = m.source ?? "okänd";
      bySource[source] = (bySource[source] || 0) + 1;
    }
    out.memory_by_source = bySource;

    const cfg = (await rest("system_config?select=key,value,updated_at", signal)).rows as {
      key: string; value: string; updated_at: string;
    }[];
    const flags: Record<string, unknown> = {};
    for (const c of cfg) flags[c.key] = { value: c.value, updated_at: c.updated_at };
    out.system_config = flags;
    out.autonomy_enabled = String(
      (flags["autonomy_enabled"] as { value?: string } | undefined)?.value ?? "",
    ) === "true";

    out.latest_memory = (await rest(
      "jarvis_memory?select=id,title,source,kind,created_at,content&order=created_at.desc&limit=6",
      signal,
    )).rows.map((r) => {
      const x = r as Record<string, unknown>;
      return { ...x, content: String(x.content ?? "").slice(0, 280) };
    });

    out.latest_runs = (await rest(
      "memory_episode?select=title,summary,started_at,source_systems,source_urls&episode_type=eq.jarvis_run&order=created_at.desc&limit=8",
      signal,
    )).rows;

    const chRows = (await rest(
      "connector_health?select=connector,status,e2e_verified,details,checked_at&order=checked_at.desc&limit=200",
      signal,
    )).rows as {
      connector: string; status: string; e2e_verified: boolean;
      details: Record<string, unknown>; checked_at: string;
    }[];
    const latestBatch = chRows[0]?.details?.batch;
    out.connector_health = {
      batch: latestBatch ?? null,
      rows: chRows
        .filter((r) => r.details?.batch === latestBatch)
        .map((r) => ({
          connector: r.connector,
          status: r.status,
          e2e_verified: r.e2e_verified,
          ring: r.details?.ring,
          level: r.details?.level,
          checked_at: r.checked_at,
        })),
    };

    out.approvals = {
      pending: (await rest(
        "approval_request?select=id,request_type,risk_class,requested_at,expires_at&response=is.null&order=requested_at.desc&limit=20",
        signal,
      )).rows,
    };
    out.tenant_usage = (await rest(
      "jarvis_tenant_usage?select=*&order=created_at.desc&limit=12",
      signal,
    ).catch(() => ({ rows: [] }))).rows;

    return json(out);
  } catch (e) {
    return json({
      error: "Brain read failed",
      detail: String((e as Error).message ?? e).slice(0, 120),
      mode: out.mode,
    }, 502);
  }
});
