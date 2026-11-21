// Klient mot jarvis-dashboard-api. Nyckeln hålls i minnet eller i flikens sessionStorage.

export const API_URL =
  (import.meta.env.VITE_JARVIS_API_URL as string | undefined) ??
  "https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-dashboard-api";

const KEY_STORAGE = "jarvis.dashboard.key";

// Äldre localStorage-kopia rensas, aldrig läses in. Ny inloggning kan krävas.
let memKey = "";
function clearLegacyKey() {
  try { localStorage.removeItem(KEY_STORAGE); } catch { /* blockerad lagring */ }
}
export function getKey(): string {
  clearLegacyKey();
  if (memKey) return memKey;
  try { memKey = sessionStorage.getItem(KEY_STORAGE) ?? ""; } catch { /* blockerad lagring */ }
  return memKey;
}
export function setKey(k: string) {
  clearLegacyKey();
  memKey = k;
  try {
    k ? sessionStorage.setItem(KEY_STORAGE, k) : sessionStorage.removeItem(KEY_STORAGE);
  } catch { /* blockerad lagring */ }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export async function call<T = unknown>(action: string, body: Record<string, unknown> = {}, signal?: AbortSignal): Promise<T> {
  const r = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-jarvis-key": getKey() },
    body: JSON.stringify({ action, ...body }),
    signal,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, (data as { error?: string }).error ?? `HTTP ${r.status}`);
  return data as T;
}

export type DashRow = {
  category: string; initiative_name?: string; initiative_status?: string; initiative_owner?: string;
  next_step?: string; next_step_deadline?: string; kpi_type?: string; kpi_value?: number; kpi_unit?: string;
  kpi_target?: number; system_name?: string; system_status?: string; system_last_check?: string; updated_at?: string;
};
export type Chat = {
  id: string; question: string; answer?: string | null; status: string; tier: string; mode: string;
  provider?: string | null; model?: string | null; quality?: number | null; cost_sek?: number | null;
  latency_ms?: number | null; run_url?: string | null; error?: string | null; created_at: string; answered_at?: string | null;
};
export type State = {
  generated_at: string;
  autonomy: boolean | null;
  config: { key: string; value: string; updated_at: string }[];
  initiatives: DashRow[]; kpis: DashRow[]; systems: DashRow[];
  episodes: { episode_type: string; title: string; summary?: string; started_at: string; source_systems?: string[] }[];
  events: { last24h: number; by_type: Record<string, number>; latest: { event_type: string; source: string; classification?: string; occurred_at: string }[] };
  connector_health: { connector: string; status: string; latency_ms?: number; scopes_ok?: boolean; e2e_verified?: boolean; checked_at: string }[];
  chats: Chat[];
  approvals_pending: unknown[];
  memory_chunks: number;
  has_llm: boolean;
  errors: string[];
};
