// JARVIS Approval Admin: a separate owner-authenticated approval endpoint.
// Deployment requires a verified Supabase Auth user AND a manually provisioned
// jarvis_approval_admin membership. No public sign-up grants approval privileges.
// All privileged DB calls use server credentials to one pinned Supabase origin.
// This endpoint approves/rejects only; it never executes an agent task.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ORIGIN = "https://fzmnqvmfilqizzftphbt.supabase.co";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
// Existing database tenant/principal IDs may be non-RFC4122 sentinel UUIDs.
const DB_UUID = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const ALLOWED_ACTIONS = new Set(["list", "decide"]);

function reply(obj, status, cors = {}) {
  return new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...cors },
  });
}

function corsFor(req) {
  const origin = req.headers.get("origin");
  if (!origin) return {};
  const allowed = (Deno.env.get("JARVIS_APPROVAL_ALLOWED_ORIGINS") || "")
    .split(",").map((o) => o.trim()).filter(Boolean);
  if (!allowed.includes(origin)) return null;
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Max-Age": "300",
    "Vary": "Origin",
  };
}

function pinnedUrl() {
  const v = (Deno.env.get("SUPABASE_URL") || "").trim();
  if (v !== ORIGIN && v !== ORIGIN + "/") throw new Error("backend_config");
  return ORIGIN;
}

function backendHeaders() {
  const modern = (Deno.env.get("SUPABASE_SECRET_KEY") || "").trim();
  const legacy = (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "").trim();
  if (modern) {
    if (!modern.startsWith("sb_secret_")) throw new Error("backend_config");
    return { apikey: modern, "Content-Type": "application/json", Accept: "application/json" };
  }
  // Legacy backend access only when its decoded *claimed* role is service_role.
  // The Supabase API validates the signature, not this local decoding.
  const parts = legacy.split(".");
  let role = "";
  try { role = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"))).role; }
  catch { /* malformed / absent */ }
  if (parts.length !== 3 || role !== "service_role") throw new Error("backend_config");
  return { apikey: legacy, Authorization: "Bearer " + legacy, "Content-Type": "application/json", Accept: "application/json" };
}

function publicKey() {
  const k = (Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ||
             Deno.env.get("SUPABASE_ANON_KEY") || "").trim();
  if (k.startsWith("sb_publishable_")) return k;
  if (k.startsWith("sb_secret_")) throw new Error("backend_config");
  try {
    const parts = k.split(".");
    const role = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"))).role;
    if (parts.length === 3 && role === "anon") return k;
  } catch { /* not anon */ }
  throw new Error("backend_config");
}

async function verifiedUser(jwt) {
  // The ID is ONLY taken from Supabase Auth's authenticated /user response.
  if (typeof jwt !== "string" || jwt.length < 16 || jwt.length > 4096) return null;
  const r = await fetch(pinnedUrl() + "/auth/v1/user", {
    method: "GET", redirect: "error",
    headers: { apikey: publicKey(), Authorization: "Bearer " + jwt, Accept: "application/json" },
    signal: AbortSignal.timeout(8000),
  });
  if (!r.ok) return null;
  const data = await r.json().catch(() => null);
  return data && typeof data.id === "string" && UUID.test(data.id) ? data.id : null;
}

async function backend(path, method = "GET", body = null) {
  // Callers construct paths exclusively from static strings / validated UUIDs.
  const r = await fetch(pinnedUrl() + "/rest/v1/" + path, {
    method, redirect: "error",
    headers: { ...backendHeaders(), ...(method === "POST" ? { Prefer: "return=representation" } : {}) },
    ...(body === null ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(8000),
  });
  if (!r.ok) throw new Error("backend_rejected");
  return await r.json();
}

async function adminFor(authUid) {
  const rows = await backend(
    "jarvis_approval_admin?select=tenant_id,principal_id&auth_user_id=eq." +
    authUid + "&enabled=is.true&limit=1"
  );
  return Array.isArray(rows) && rows.length === 1 && DB_UUID.test(rows[0].tenant_id)
    && DB_UUID.test(rows[0].principal_id) ? rows[0] : null;
}

async function listPending(tenant) {
  const now = encodeURIComponent(new Date().toISOString());
  const decisions = await backend(
    "approval_decision?select=id,title,risk_class,status,expires_at,draft_ref" +
    "&tenant_id=eq." + tenant + "&status=eq.pending_approval" +
    "&expires_at=gt." + now + "&order=created_at.desc&limit=30"
  );
  if (!Array.isArray(decisions) || decisions.length === 0) return [];
  const byId = new Map(decisions.filter((d) => UUID.test(d.id)).map((d) => [d.id, d]));
  if (byId.size === 0) return [];
  const ids = Array.from(byId.keys()).join(",");
  const requests = await backend(
    "approval_request?select=id,decision_id,risk_class,expires_at,response,requested_at" +
    "&decision_id=in.(" + ids + ")&response=is.null&expires_at=gt." + now +
    "&order=requested_at.desc&limit=30"
  );
  return (Array.isArray(requests) ? requests : [])
    .filter((r) => byId.has(r.decision_id) && UUID.test(r.id))
    .map((r) => {
      const d = byId.get(r.decision_id);
      return {
        request_id: r.id, title: String(d.title).slice(0,120),
        risk_class: r.risk_class, expires_at: r.expires_at,
        action_bound: typeof d.draft_ref === "string" && /^sha256:[a-f0-9]{64}$/.test(d.draft_ref),
      };
    });
}

// Limit the *actual UTF-8 bytes* read, even when Content-Length is missing
// or wrong. Do not buffer unbounded, attacker-controlled request bodies.
async function readBodyLimited(req, maxBytes) {
  if (!req.body) return "";
  const reader = req.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel().catch(() => {});
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const merged = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(merged);
  } catch {
    return null;
  }
}

Deno.serve(async (req) => {
  const cors = corsFor(req);
  if (!cors) return reply({ error: "Forbidden" }, 403);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "POST" || new URL(req.url).search) {
    return reply({ error: "Method or URL not permitted" }, 405, cors);
  }
  try {
    const length = Number(req.headers.get("content-length") || "0");
    if (!Number.isSafeInteger(length) || length < 0 || length > 4096) return reply({ error: "Invalid payload" }, 413, cors);
    const auth = req.headers.get("authorization") || "";
    if (!/^Bearer [A-Za-z0-9._~-]+$/.test(auth)) return reply({ error: "Unauthorized" }, 401, cors);
    const id = await verifiedUser(auth.slice(7));
    if (!id) return reply({ error: "Unauthorized" }, 401, cors);
    const admin = await adminFor(id);
    if (!admin) return reply({ error: "Forbidden" }, 403, cors);

    const raw = await readBodyLimited(req, 4096);
    if (raw === null) return reply({ error: "Invalid payload" }, 413, cors);
    const body = JSON.parse(raw);
    if (!body || typeof body !== "object" || Array.isArray(body)
        || !ALLOWED_ACTIONS.has(body.action)) return reply({ error: "Invalid action" }, 400, cors);
    if (body.action === "list") {
      return reply({ pending: await listPending(admin.tenant_id) }, 200, cors);
    }
    if (!UUID.test(body.request_id || "") ||
        !["approved", "rejected"].includes(body.decision) ||
        (body.reason !== undefined && (typeof body.reason !== "string" || body.reason.length > 500))) {
      return reply({ error: "Invalid decision" }, 400, cors);
    }
    // The requesting client cannot supply actor or tenant; we derive authUid
    // via verifiedUser() and the DB RPC checks owner, tenant and current state
    // transactionally under row locks, including expiry and action fingerprint.
    const result = await backend("rpc/jarvis_approval_decide", "POST", {
      p_auth_user_id: id, p_request_id: body.request_id,
      p_response: body.decision, p_reason: body.reason || null,
    });
    return reply({ request_id: result.request_id, response: result.response }, 200, cors);
  } catch {
    // Fail closed: do not forward database messages, credentials or sensitive data.
    return reply({ error: "Approval service unavailable" }, 503, cors);
  }
});
