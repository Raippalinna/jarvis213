// JARVIS Brain – read-only status endpoint with minimal public response.
// Public mode returns only a health marker. Private mode requires x-jarvis-key.
// Query-string authentication is deliberately rejected before any database access.
// No writes are performed; the service-role key is used only server-side in private mode.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const EXPECTED_SUPABASE_ORIGIN = "https://fzmnqvmfilqizzftphbt.supabase.co";
const ENDPOINT_KEY = Deno.env.get("JARVIS_ENDPOINT_KEY") ?? "";

type BackendCredential = { url: string; headers: Record<string, string> };

function backendCredential(): BackendCredential | null {
  const url = (Deno.env.get("SUPABASE_URL") ?? "").trim().replace(/\/+$/, "");
  const preferred = (Deno.env.get("SUPABASE_SECRET_KEY") ?? "").trim();
  const legacy = (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "").trim();
  const key = preferred || legacy;
  if (url !== EXPECTED_SUPABASE_ORIGIN || !key) return null;
  const modern = key.startsWith("sb_secret_");
  if (preferred && !modern) return null;
  if (key.startsWith("sb_publishable_")) return null;
  if (!modern) {
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
  const headers: Record<string, string> = { apikey: key, Accept: "application/json" };
  if (!modern) headers.Authorization = "Bearer " + key;
  return { url, headers };
}

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, x-jarvis-key",
  "Cache-Control": "no-store",
};

async function rest(
  backend: BackendCredential,
  path: string,
  signal: AbortSignal,
): Promise<{ rows: unknown[]; count: number | null }> {
  const r = await fetch(backend.url + "/rest/v1/" + path, {
    signal,
    redirect: "error",
    headers: { ...backend.headers, Prefer: "count=exact", Accept: "application/json" },
  });
  if (!r.ok) throw new Error("upstream_unavailable");
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
  if (req.method !== "GET") {
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

  const backend = backendCredential();
  if (!backend) {
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
      rest(backend, "event?select=event_id&limit=1", signal),
      rest(backend, "memory_episode?select=id&limit=1", signal),
      rest(backend, "jarvis_memory?select=id&limit=1", signal),
      rest(backend, "connector_health?select=id&limit=1", signal),
      rest(backend, "approval_request?select=id&limit=1", signal),
    ]);
    out.counts = {
      event: ev.count,
      memory_episode: ep.count,
      jarvis_memory: mem.count,
      connector_health: ch.count,
      approval_request: ap.count,
    };

    const since = new Date(Date.now() - 14 * 864e5).toISOString();
    const evRows = (await rest(backend, "event?select=occurred_at,event_type&occurred_at=gte." + since + "&order=occurred_at.desc&limit=2000",
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

    const memRows = (await rest(backend, "jarvis_memory?select=source,kind,sensitivity&limit=5000",
      signal,
    )).rows as { source: string; kind: string; sensitivity: string }[];
    const bySource: Record<string, number> = {};
    for (const m of memRows) {
      const source = m.source ?? "okänd";
      bySource[source] = (bySource[source] || 0) + 1;
    }
    out.memory_by_source = bySource;

    const autonomyRows = (await rest(
      backend, "system_config?key=eq.autonomy_enabled&select=value,updated_at", signal,
    )).rows as { value: string | boolean; updated_at: string }[];
    out.autonomy_enabled = autonomyRows.length === 1 &&
      (autonomyRows[0].value === "true" || autonomyRows[0].value === true);
    out.autonomy_checked_at = autonomyRows[0]?.updated_at ?? null;

    out.latest_memory_metadata = (await rest(
      backend, "jarvis_memory?select=id,title,source,kind,created_at,sensitivity&sensitivity=in.(public,internal)&order=created_at.desc&limit=6",
      signal,
    )).rows;

    out.latest_runs = (await rest(backend, "memory_episode?select=title,episode_type,started_at&episode_type=eq.jarvis_run&order=created_at.desc&limit=8",
      signal,
    )).rows;

    const chRows = (await rest(backend, "connector_health?select=connector,status,e2e_verified,details,checked_at&order=checked_at.desc&limit=200",
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

    const pending = await rest(
      backend, "approval_request?select=id&response=is.null&limit=1", signal,
    );
    out.approvals_pending_count = pending.count;
    return json(out);
  } catch (e) {
    return json({ error: "Brain read failed", mode: out.mode }, 502);
  }
});
