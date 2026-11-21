import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, call, getKey, setKey, type Chat, type State } from "./api";
import { Badge, Panel, Ring, Spark, StatusDot, fmt, fmtTime, timeAgo } from "./components";
import { JarvisOrb } from "./JarvisOrb";
import { PerplexityComputerHandoff } from "./PerplexityComputerHandoff";
import type { OrbMode } from "./orb";
import { isSpeaking, listen, listenSupported, onVoice, speak, stopSpeaking, voiceSupported } from "./voice";

function loadPref(k: string, d: string) { try { return localStorage.getItem(k) ?? d; } catch { return d; } }
function savePref(k: string, v: string) { try { localStorage.setItem(k, v); } catch { /* sandlåda */ } }
function useOrbSize(large: number, small: number) {
  const [sz, setSz] = useState(() => (typeof window !== "undefined" && window.innerWidth < 640 ? small : large));
  useEffect(() => { const f = () => setSz(window.innerWidth < 640 ? small : large); window.addEventListener("resize", f); return () => window.removeEventListener("resize", f); }, [large, small]);
  return sz;
}

type Tab = "oversikt" | "chatt" | "system" | "minne";

export default function App() {
  const [key, setKeyState] = useState(getKey());
  const [state, setState] = useState<State | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<Tab>("oversikt");
  const [voiceOn, setVoiceOn] = useState(() => loadPref("jarvis.voice", voiceSupported ? "1" : "0") === "1");
  useEffect(() => { savePref("jarvis.voice", voiceOn ? "1" : "0"); if (!voiceOn) stopSpeaking(); }, [voiceOn]);

  const refresh = useCallback(async () => {
    if (!getKey()) return;
    setLoading(true);
    try {
      const s = await call<State>("state");
      setState(s); setErr(null);
    } catch (e) {
      const ae = e as ApiError;
      const network = !(e instanceof ApiError);
      setErr(ae.status === 401 ? "Fel nyckel. Ange din Jarvis-nyckel igen."
        : network ? "Jarvis-API:t svarar inte. Edge-funktionen jarvis-dashboard-api verkar inte vara driftsatt eller nås inte."
        : ae.message || "Kunde inte hämta status");
      if (ae.status === 401) { setKey(""); setKeyState(""); }
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 60_000); return () => clearInterval(t); }, [refresh]);
  useEffect(() => {
    // Sandlådad iframe (t.ex. förhandsvisning) kastar SecurityError redan vid läsning av navigator.serviceWorker
    try { if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js").catch(() => {}); } catch { /* ingen SW här */ }
  }, []);

  if (!key) return <Login onDone={(k) => { setKey(k); setKeyState(k); setTimeout(refresh, 0); }} error={err} />;

  const thinking = state?.chats?.some((c) => c.status === "queued" || c.status === "running") ?? false;
  const coreState: OrbMode = err ? "offline" : thinking ? "thinking" : "idle";

  return (
    <div className="min-h-full bg-grid aurora">
      <header className="sticky top-0 z-20 backdrop-blur-md bg-bg/70 border-b border-line">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-cyan pulse text-cyan" />
            <h1 className="font-bold tracking-[0.25em] text-sm md:text-base text-glow">JARVIS Ω∞</h1>
            <span className="hidden md:inline text-muted text-xs">RICKY OS · kontrollrum</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            {state && <Badge tone={state.autonomy ? "lime" : state.autonomy === false ? "rose" : "amber"}>autonomi {state.autonomy === null ? "okänd" : state.autonomy ? "på" : "paus"}</Badge>}
            {voiceSupported && <button onClick={() => setVoiceOn((v) => !v)} className={`px-2 py-1 rounded-md border ${voiceOn ? "border-cyan/60 text-cyan" : "border-line text-muted"}`} aria-pressed={voiceOn} title="Jarvis läser upp svaren">röst {voiceOn ? "på" : "av"}</button>}
            <button onClick={refresh} className="px-2 py-1 rounded-md border border-line text-muted hover:text-ink" aria-label="Uppdatera">{loading ? "…" : "↻"}</button>
            <button onClick={() => { setKey(""); setKeyState(""); }} className="hidden md:inline px-2 py-1 rounded-md border border-line text-muted hover:text-ink">Logga ut</button>
          </div>
        </div>
        <nav className="max-w-6xl mx-auto px-4 hidden md:flex gap-1 pb-2">
          {tabs.map((t) => <TabBtn key={t.id} active={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</TabBtn>)}
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-4 safe-bottom">
        {err && <div className="panel p-3 mb-4 border-rose/40 text-rose text-sm">{err}</div>}
        {!state && !err && <div className="text-muted text-sm py-10 text-center">Kopplar upp mot Jarvis…</div>}
        {state && tab === "oversikt" && <Overview state={state} coreState={coreState} onAsk={() => setTab("chatt")} />}
        {state && tab === "chatt" && <ChatView state={state} onChanged={refresh} coreState={coreState} voiceOn={voiceOn} />}
        {state && tab === "system" && <Systems state={state} />}
        {state && tab === "minne" && <Memory state={state} />}
      </main>

      <nav className="md:hidden fixed bottom-0 inset-x-0 z-20 border-t border-line bg-bg/85 backdrop-blur-md" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
        <div className="grid grid-cols-4">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`py-3 text-[11px] tracking-wider uppercase ${tab === t.id ? "text-cyan" : "text-muted"}`}>
              <div className="text-base leading-none mb-1">{t.icon}</div>{t.label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}

const tabs: { id: Tab; label: string; icon: string }[] = [
  { id: "oversikt", label: "Översikt", icon: "◉" },
  { id: "chatt", label: "Jarvis", icon: "◈" },
  { id: "system", label: "System", icon: "⬡" },
  { id: "minne", label: "Minne", icon: "≋" },
];

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return <button onClick={onClick} className={`px-3 py-1.5 rounded-full text-xs tracking-widest uppercase border ${active ? "border-cyan/50 text-cyan glow-cyan" : "border-line text-muted hover:text-ink"}`}>{children}</button>;
}

function Login({ onDone, error }: { onDone: (k: string) => void; error: string | null }) {
  const [v, setV] = useState("");
  return (
    <div className="min-h-full bg-grid flex items-center justify-center p-6">
      <form onSubmit={(e) => { e.preventDefault(); if (v.trim()) onDone(v.trim()); }} className="panel p-6 w-full max-w-sm text-center">
        <JarvisOrb mode="idle" size={220} />
        <h1 className="mt-2 font-bold tracking-[0.3em] text-glow">JARVIS Ω∞</h1>
        <p className="text-muted text-sm mt-1 mb-5">Ange din Jarvis-nyckel. Den sparas bara i den här webbläsaren.</p>
        <input type="password" value={v} onChange={(e) => setV(e.target.value)} placeholder="Jarvis-nyckel" autoFocus
          className="w-full px-3 py-2.5 rounded-lg bg-black/40 border border-line focus:border-cyan/60 outline-none mono" />
        {error && <div className="text-rose text-xs mt-2">{error}</div>}
        <button className="mt-4 w-full py-2.5 rounded-lg bg-cyan/90 text-bg font-semibold hover:bg-cyan">Öppna kontrollrummet</button>
      </form>
    </div>
  );
}

function Overview({ state, coreState, onAsk }: { state: State; coreState: OrbMode; onAsk: () => void }) {
  const orbSize = useOrbSize(320, 260);
  const kpiSeries = useMemo(() => state.episodes.filter((e) => e.episode_type === "kpi_snapshot").map((e) => Number(/(\d+) events/.exec(e.summary ?? "")?.[1] ?? 0)).reverse(), [state.episodes]);
  const sysOk = state.systems.filter((s) => /operational/.test(s.system_status ?? "")).length;
  const healthOk = state.connector_health.filter((h) => h.status === "healthy").length;
  const lastChat = state.chats[0];
  return (
    <div className="grid gap-4 md:grid-cols-12">
      <Panel className="md:col-span-4 text-center hero">
        <JarvisOrb mode={coreState} size={orbSize} />
        <div className="text-xs tracking-widest uppercase text-muted">{coreState === "thinking" ? "JARVIS Prime arbetar" : coreState === "offline" ? "frånkopplad" : "online · lyssnar"}</div>
        <div className="mono text-[11px] text-muted mt-1">uppdaterad {timeAgo(state.generated_at) === "nu" ? "just nu" : `för ${timeAgo(state.generated_at)} sedan`}</div>
        <button onClick={onAsk} className="mt-4 w-full py-2.5 rounded-lg border border-cyan/50 text-cyan hover:bg-cyan/10 text-sm tracking-wider">Prata med Jarvis →</button>
      </Panel>

      <Panel title="KPI" className="md:col-span-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {state.kpis.map((k) => <Ring key={k.kpi_type} label={kpiLabel(k.kpi_type)} value={Number(k.kpi_value ?? 0)} target={k.kpi_target ?? undefined} unit={unitLabel(k.kpi_unit)} lowerIsBetter={/^time_to_/.test(k.kpi_type ?? "")} />)}
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
          <div><div className="text-[11px] uppercase tracking-widest text-muted">händelser 24 h</div><div className="mono text-xl">{state.events.last24h}</div></div>
          <Spark values={kpiSeries} />
          <div className="text-right"><div className="text-[11px] uppercase tracking-widest text-muted">minne</div><div className="mono text-xl">{state.memory_chunks}<span className="text-xs text-muted ml-1">chunks</span></div></div>
        </div>
      </Panel>

      <Panel title="Initiativ" className="md:col-span-7">
        <ul className="divide-y divide-line">
          {state.initiatives.map((i) => (
            <li key={i.initiative_name} className="py-2.5 flex items-start gap-3">
              <StatusDot status={i.initiative_status} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2"><span className="font-medium truncate">{i.initiative_name}</span>{i.next_step_deadline && <Badge tone="amber">{i.next_step_deadline}</Badge>}</div>
                <div className="text-sm text-muted truncate">{i.next_step || "–"}</div>
              </div>
            </li>
          ))}
        </ul>
      </Panel>

      <div className="md:col-span-5 grid gap-4">
        <Panel title="Systemläge" right={<Badge tone={sysOk === state.systems.length ? "lime" : "amber"}>{sysOk}/{state.systems.length} operativa</Badge>}>
          <div className="flex flex-wrap gap-1.5">
            {state.systems.map((s) => <span key={s.system_name} className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-line text-xs"><StatusDot status={s.system_status} />{s.system_name}</span>)}
          </div>
        </Panel>
        <Panel title="Kopplingar" right={<Badge tone={healthOk === state.connector_health.length ? "lime" : "amber"}>{healthOk}/{state.connector_health.length} friska</Badge>}>
          <div className="text-xs text-muted">senast kontrollerad {fmtTime(state.connector_health[0]?.checked_at)} · {state.approvals_pending.length} väntande godkännanden</div>
        </Panel>
        {lastChat && (
          <Panel title="Senaste svar">
            <div className="text-sm font-medium truncate">{lastChat.question}</div>
            <div className="text-sm text-muted mt-1 line-clamp-4 whitespace-pre-wrap">{lastChat.answer ?? (lastChat.status === "failed" ? `Misslyckades: ${lastChat.error ?? ""}` : "väntar på JARVIS Prime…")}</div>
            <div className="mt-2 flex gap-2"><Badge tone={lastChat.status === "answered" ? "lime" : lastChat.status === "failed" ? "rose" : "amber"}>{lastChat.status}</Badge><Badge>{lastChat.mode} · {lastChat.tier}</Badge></div>
          </Panel>
        )}
      </div>
    </div>
  );
}

function kpiLabel(t?: string) { return ({ cashflow: "Kassaflöde", time_to_revenue: "Tid till intäkt", automation_level: "Automationsgrad", time_to_demo: "Tid till demo" } as Record<string, string>)[t ?? ""] ?? (t ?? "KPI"); }
function unitLabel(u?: string) { return ({ SEK: "kr", days: "dagar", percent: "%" } as Record<string, string>)[u ?? ""] ?? (u ?? ""); }

function ChatView({ state, onChanged, coreState, voiceOn }: { state: State; onChanged: () => void; coreState: OrbMode; voiceOn: boolean }) {
  const [msg, setMsg] = useState("");
  const [listening, setListening] = useState(false);
  const stopListen = useRef<(() => void) | null>(null);
  const spoken = useRef<Set<string>>(new Set());
  const mounted = useRef(false);
  const orbSize = useOrbSize(150, 130);
  const [tier, setTier] = useState<"FREE" | "LOW" | "MED" | "HIGH">("LOW");
  const [mode, setMode] = useState<"auto" | "prime" | "instant">("auto");
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState<Chat[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const chats = useMemo(() => {
    const map = new Map<string, Chat>();
    for (const c of [...state.chats, ...local]) map.set(c.id, { ...(map.get(c.id) ?? {} as Chat), ...c });
    return [...map.values()].sort((a, b) => a.created_at.localeCompare(b.created_at));
  }, [state.chats, local]);

  // Polla pågående frågor
  useEffect(() => {
    const pending = chats.filter((c) => c.status === "queued" || c.status === "running");
    if (pending.length === 0) return;
    const t = setInterval(async () => {
      for (const p of pending) {
        try { const c = await call<Chat>("chat_get", { id: p.id }); setLocal((l) => [...l.filter((x) => x.id !== c.id), c]); if (c.status === "answered" || c.status === "failed") onChanged(); }
        catch { /* försök igen */ }
      }
    }, 6000);
    return () => clearInterval(t);
  }, [chats, onChanged]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [chats.length]);

  // Läs upp nya svar (inte de som redan fanns vid inladdning)
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; chats.forEach((c) => spoken.current.add(c.id)); return; }
    for (const c of chats) {
      if (c.status === "answered" && c.answer && !spoken.current.has(c.id)) {
        spoken.current.add(c.id);
        if (voiceOn) speak(c.answer);
      }
    }
  }, [chats, voiceOn]);

  // Röstinmatning: transkript → textfält; slutgiltigt → skicka
  const sendRef = useRef<() => void>(() => {});
  useEffect(() => onVoice((ev) => {
    if (ev.type === "transcript") { setMsg(ev.text); if (ev.final) setTimeout(() => sendRef.current(), 150); }
    if (ev.type === "listen-end") setListening(false);
  }), []);
  function toggleListen() {
    if (listening) { stopListen.current?.(); stopListen.current = null; setListening(false); return; }
    stopSpeaking();
    const stop = listen();
    if (!stop) { setNote("Röstinmatning stöds inte i den här webbläsaren."); return; }
    stopListen.current = stop; setListening(true);
  }

  async function send() {
    const m = msg.trim(); if (!m || busy) return;
    setBusy(true); setNote(null);
    try {
      const history = chats.filter((c) => c.answer).slice(-6).flatMap((c) => [{ role: "user", content: c.question }, { role: "assistant", content: c.answer! }]);
      const r = await call<Chat & { eta_seconds?: number }>("chat_send", { message: m, tier, mode, history });
      setLocal((l) => [...l, { ...r, question: m, tier, mode: r.mode, created_at: new Date().toISOString() }]);
      setMsg("");
      if (r.status === "queued") setNote(`Skickat till JARVIS Prime (${tier}). Svar väntas inom ~${r.eta_seconds ?? 60} s.`);
    } catch (e) {
      const ae = e as ApiError;
      setNote(ae.status === 423 ? "Autonomi är pausad – Jarvis dispatchar inget just nu." : `Fel: ${ae.message}`);
    } finally { setBusy(false); }
  }
  sendRef.current = send;

  return (
    <div className="grid gap-4 md:grid-cols-12">
      <Panel className="md:col-span-8 flex flex-col min-h-[60vh]">
        <div className="flex items-center gap-3 border-b border-line pb-2 mb-2">
          <JarvisOrb mode={coreState} size={orbSize} className="-my-6 -ml-4 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs tracking-widest uppercase text-muted">{listening ? "lyssnar…" : coreState === "thinking" ? "JARVIS Prime arbetar" : coreState === "offline" ? "frånkopplad" : "redo"}</div>
            <div className="text-[11px] text-muted mt-0.5">{voiceOn ? "Jarvis läser upp nya svar." : "Röst av – tryck ”röst” i toppen för uppläsning."}{listenSupported ? " Tala genom mikrofonknappen." : ""}</div>
          </div>
          {isSpeaking() && <button onClick={stopSpeaking} className="ml-auto text-xs px-2 py-1 rounded-md border border-line text-muted">tyst</button>}
        </div>
        <div className="flex-1 overflow-y-auto scroll-thin space-y-4 pr-1">
          {chats.length === 0 && <div className="text-muted text-sm text-center py-10">Inga samtal än. Ställ din första fråga till Jarvis.</div>}
          {chats.map((c) => (
            <div key={c.id} className="space-y-2">
              <div className="flex justify-end"><div className="max-w-[85%] px-3 py-2 rounded-2xl rounded-tr-sm bg-cyan/10 border border-cyan/30 text-sm whitespace-pre-wrap">{c.question}</div></div>
              <div className="flex justify-start">
                <div className="max-w-[92%] px-3 py-2 rounded-2xl rounded-tl-sm bg-violet/10 border border-violet/30 text-sm whitespace-pre-wrap">
                  {c.answer ?? (c.status === "failed" ? <span className="text-rose">Misslyckades: {c.error ?? "okänt fel"}</span> : <span className="text-muted">JARVIS Prime arbetar<span className="blink">…</span></span>)}
                  <div className="mt-2 flex flex-wrap gap-1.5 items-center">
                    <Badge tone={c.status === "answered" ? "lime" : c.status === "failed" ? "rose" : "amber"}>{c.status}</Badge>
                    <Badge>{c.mode}{c.tier ? ` · ${c.tier}` : ""}</Badge>
                    {c.model && <Badge tone="violet">{c.provider ? `${c.provider}/` : ""}{c.model}</Badge>}
                    {c.quality != null && <Badge>kvalitet {fmt(c.quality)}</Badge>}
                    {c.cost_sek != null && <Badge>{fmt(c.cost_sek)} kr</Badge>}
                    {c.latency_ms != null && <Badge>{fmt(c.latency_ms / 1000)} s</Badge>}
                    {c.run_url && <a href={c.run_url} target="_blank" rel="noreferrer" className="text-[11px] text-cyan underline">körning</a>}
                    {voiceSupported && c.answer && <button onClick={() => speak(c.answer!)} className="text-[11px] text-muted hover:text-cyan" title="Läs upp">läs upp</button>}
                    <span className="text-[11px] text-muted ml-auto mono">{fmtTime(c.answered_at ?? c.created_at)}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          <div ref={bottom} />
        </div>
        <div className="mt-3 border-t border-line pt-3">
          {note && <div className="text-xs text-amber mb-2">{note}</div>}
          <div className="flex gap-2">
            <textarea value={msg} onChange={(e) => setMsg(e.target.value)} rows={2} placeholder="Fråga Jarvis…"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              className="flex-1 px-3 py-2 rounded-lg bg-black/40 border border-line focus:border-cyan/60 outline-none text-sm resize-none" />
            {listenSupported && <button onClick={toggleListen} className={`px-3 rounded-lg border ${listening ? "border-lime text-lime mic-live" : "border-line text-muted hover:text-ink"}`} aria-pressed={listening} title="Tala till Jarvis">{listening ? "●" : "mik"}</button>}
            <button onClick={send} disabled={busy || !msg.trim()} className="px-4 rounded-lg bg-cyan/90 text-bg font-semibold disabled:opacity-40">{busy ? "…" : "Skicka"}</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 items-center text-xs">
            <span className="text-muted">Tier</span>
            {(["FREE", "LOW", "MED", "HIGH"] as const).map((t) => <button key={t} onClick={() => setTier(t)} className={`px-2 py-0.5 rounded-full border mono ${tier === t ? "border-cyan/60 text-cyan" : "border-line text-muted"}`}>{t}</button>)}
            <span className="text-muted ml-2">Läge</span>
            {(["auto", "prime", "instant"] as const).map((m) => <button key={m} onClick={() => setMode(m)} disabled={m === "instant" && !state.has_llm} title={m === "instant" && !state.has_llm ? "Kräver LLM_API_KEY i Supabase secrets" : ""} className={`px-2 py-0.5 rounded-full border mono disabled:opacity-30 ${mode === m ? "border-violet/70 text-violet" : "border-line text-muted"}`}>{m}</button>)}
          </div>
        </div>
      </Panel>
      <div className="md:col-span-4 grid gap-4 content-start">
        <Panel title="Så svarar Jarvis">
          <ul className="text-sm text-muted space-y-2">
            <li><span className="text-ink">prime</span> – frågan körs i JARVIS Prime (GitHub Actions, LangGraph, Frugality Agent) och loggas i Notion Control Room. 40–120 s.</li>
            <li><span className="text-ink">instant</span> – direktsvar via LLM-gateway. {state.has_llm ? "Aktivt." : "Inaktivt: lägg secret LLM_API_KEY (valfritt LLM_BASE_URL, LLM_MODEL) i Supabase."}</li>
            <li><span className="text-ink">auto</span> – instant om det finns, annars prime.</li>
          </ul>
        </Panel>
        <Panel title="Kostnadsdimmer">
          <div className="text-sm text-muted">FREE: Cerebras/Groq · LOW: max 1 kr · MED: max 10 kr · HIGH: max 50 kr per anrop. Månadsbudget 200 kr enligt <span className="mono">providers.yaml</span>.</div>
        </Panel>
      </div>
    </div>
  );
}

function Systems({ state }: { state: State }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <PerplexityComputerHandoff />
      <Panel title="System (jarvis_dashboard_v2)">
        <ul className="divide-y divide-line">{state.systems.map((s) => (
          <li key={s.system_name} className="py-2 flex items-center justify-between gap-2"><span className="flex items-center gap-2"><StatusDot status={s.system_status} />{s.system_name}</span><span className="text-xs text-muted mono">{s.system_status} · {timeAgo(s.system_last_check ?? s.updated_at)}</span></li>
        ))}</ul>
      </Panel>
      <Panel title="Connector-hälsa (connector_health)">
        <ul className="divide-y divide-line">{state.connector_health.map((h) => (
          <li key={h.connector} className="py-2 flex items-center justify-between gap-2"><span className="flex items-center gap-2"><StatusDot status={h.status} />{h.connector}</span><span className="text-xs text-muted mono">{h.status}{h.e2e_verified ? " · e2e" : ""}{h.latency_ms ? ` · ${h.latency_ms} ms` : ""}</span></li>
        ))}</ul>
      </Panel>
      <Panel title="Systemkonfiguration">
        <ul className="divide-y divide-line">{state.config.map((c) => (
          <li key={c.key} className="py-2 flex items-center justify-between gap-2 text-sm"><span className="mono">{c.key}</span><span className="text-muted mono truncate max-w-[55%]">{c.value || "–"}</span></li>
        ))}</ul>
      </Panel>
      <Panel title="Händelser 24 h" right={<Badge>{state.events.last24h}</Badge>}>
        <div className="flex flex-wrap gap-1.5 mb-3">{Object.entries(state.events.by_type).map(([t, n]) => <Badge key={t} tone="cyan">{t} × {n}</Badge>)}</div>
        <ul className="divide-y divide-line text-sm">{state.events.latest.map((e, i) => (
          <li key={i} className="py-1.5 flex justify-between gap-2"><span className="truncate">{e.event_type} <span className="text-muted">· {e.source}</span></span><span className="text-muted mono text-xs">{fmtTime(e.occurred_at)}</span></li>
        ))}</ul>
      </Panel>
    </div>
  );
}

function Memory({ state }: { state: State }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="Episoder (memory_episode)">
        <ul className="divide-y divide-line text-sm">{state.episodes.map((e, i) => (
          <li key={i} className="py-2"><div className="flex justify-between gap-2"><span className="font-medium truncate">{e.title}</span><span className="text-muted mono text-xs">{fmtTime(e.started_at)}</span></div><div className="text-muted text-xs mt-0.5">{e.episode_type}{e.summary ? ` · ${e.summary}` : ""}</div></li>
        ))}</ul>
      </Panel>
      <Panel title="Väntande godkännanden" right={<Badge tone={state.approvals_pending.length ? "amber" : "lime"}>{state.approvals_pending.length}</Badge>}>
        {state.approvals_pending.length === 0 ? <div className="text-sm text-muted">Inga öppna godkännanden i Approval Center.</div> :
          <pre className="text-xs mono text-muted whitespace-pre-wrap">{JSON.stringify(state.approvals_pending, null, 1)}</pre>}
        <div className="mt-4 text-xs text-muted">Kunskapsminne: {state.memory_chunks} chunks i <span className="mono">jarvis_memory</span> (Brain-wiki speglad 2026-08-29).</div>
        {state.errors.length > 0 && <div className="mt-3 text-xs text-rose">Delfel vid hämtning: {state.errors.join(", ")}</div>}
      </Panel>
    </div>
  );
}
