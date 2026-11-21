import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, ArrowUp, ArrowUpRight, AudioLines, Brain, Check, ChevronDown, Circle, Command, Database, Fingerprint, Layers, LockKeyhole, LogOut, Mic, Moon, Network, PanelLeftClose, Radio, RefreshCw, Search, ShieldCheck, SlidersHorizontal, Sparkles, Square, Sun, Volume2, X } from "lucide-react";
import { call, getKey, setKey, type State } from "./api";
import { Presence } from "./Presence";
import { listen, listenSupported, onVoice, speak, stopSpeaking } from "./voice";

const BRIDGE = (import.meta.env.VITE_JARVIS_BRIDGE_URL as string | undefined) || "";
type Connector = { source_id: string; name: string; status: string; read_tools: string[]; note?: string };
type Catalog = { at: string; live: boolean; connectors: Connector[] };
type Trace = { source: string; tool: string; status: string; truncated?: boolean };
type Reply = { id: string; question: string; answer: string; trace: Trace[]; model?: string; latency_ms?: number; at: string };
type View = "home" | "chat" | "memory" | "activity";
type Tone = "varm" | "gnista" | "fokus";
const toneNames = { varm: "Varm +", gnista: "Gnista", fokus: "Fokus" };
const WORK_MODES = [
  ["Djupanalys", "Sök, jämför och skilj fakta från antaganden.", "Analysera följande med tydliga källor och osäkerheter: "],
  ["Kontoengagemang", "Förbered kontakt, utan att skicka något.", "Förbered ett kontaktutkast, utan utskick, för "],
  ["Kontoprofiler", "Samla bolagsbild och intern kontext.", "Bygg en källgrundad kontoprofil för "],
  ["Dataprofilering", "Kartlägg datakvalitet före analys.", "Kartlägg datakvalitet och luckor i "],
  ["Kopplingskontroll", "Läs status, verifiera steg för steg.", "Kontrollera mitt Jarvis Supabase-projekts status och edge-funktioner."],
  ["Efterlevnad", "Identifiera krav och kontrollpunkter.", "Ta fram en kontrollista, inte juridisk rådgivning, för "],
  ["Skapa skill", "Formulera ett instruktionutkast.", "Förbered ett utkast till en skill som "],
  ["Alternativdata", "Specificera underlag för separat finansflöde.", "Beskriv vilka alternativa data som behövs för att analysera "],
  ["Webbläsarstyrning", "Kräver online-dator och Computer.", "Förbered stegen för att i Comet "],
  ["BTF-dokument", "Arbeta spårbart från original.", "Hitta relevanta originalunderlag för "],
  ["Kodgranskning", "Granska klistrad kod utan driftsättning.", "Granska denna kod, identifiera fel och föreslå tester: "],
  ["Beslutsstöd", "Alternativ, risker och nästa steg.", "Hjälp mig välja mellan följande alternativ: "],
];
function time(s?: string) { return s ? new Date(s).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" }) : "Ej kontrollerat"; }
async function bridge<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  if (!BRIDGE) throw new Error("Computer-bryggan är inte konfigurerad på denna driftsättning.");
  const r = await fetch(BRIDGE + path, { method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", "x-jarvis-key": getKey() },
    body: body === undefined ? undefined : JSON.stringify(body), signal: signal || AbortSignal.timeout(150000) });
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `Anropet avvisades (${r.status}).`); }
  return r.json();
}
function Logo() {
  return <svg width="32" height="36" viewBox="0 0 32 36" fill="none" aria-label="Jarvis"><path d="M24 3H10L3 16l7 14h14l6-12H16l-4 7M24 3v15" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round"/></svg>;
}
function RichText({ text }: { text: string }) {
  // No HTML rendering. Only explicit http(s) Markdown links are clickable.
  return <div className="answer-text">{text.split(/(\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g).map((part, i) => {
    const m = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(part);
    return m ? <a key={i} href={m[2]} target="_blank" rel="noreferrer noopener">{m[1]} <ArrowUpRight size={12}/></a> : <span key={i}>{part.replace(/\*\*/g, "")}</span>;
  })}</div>;
}

export default function App() {
  const [key, keyState] = useState(getKey());
  const [password, setPassword] = useState("");
  const [state, setState] = useState<State | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [view, setView] = useState<View>("home");
  const [drawer, setDrawer] = useState<"connections" | "skills" | "settings" | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [msg, setMsg] = useState("");
  const [replies, setReplies] = useState<Reply[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tone, setTone] = useState<Tone>("varm");
  const [autoRead, setAutoRead] = useState(false);
  const [natural, setNatural] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [dark, setDark] = useState(true);
  const [quiet, setQuiet] = useState(false);
  const [focus, setFocus] = useState(false);
  const [clock, setClock] = useState(new Date());
  const abort = useRef<AbortController | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const analyser = useRef<AnalyserNode | null>(null);
  const speechEpoch = useRef(0);
  const stopListen = useRef<(() => void) | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const available = catalog?.connectors.filter(c => c.status === "CONNECTED" && c.read_tools.length > 0) || [];
  const connectorName = (id: string) => catalog?.connectors.find(c => c.source_id === id)?.name || id;

  const refresh = useCallback(async () => {
    if (!getKey()) return;
    setLoading(true); setError("");
    try {
      const s = await call<State>("state");
      setState(s);
      try { setCatalog(await bridge<Catalog>("/api/catalog")); }
      catch (e) { setError((e as Error).message); }
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (key) void refresh(); }, [key, refresh]);
  useEffect(() => { const t = setInterval(() => setClock(new Date()), 30000); return () => clearInterval(t); }, []);
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  useEffect(() => onVoice(ev => {
    if (ev.type === "transcript") setMsg(ev.text); // Always review transcript before submitting.
    if (ev.type === "listen-end") setListening(false);
    if (ev.type === "start") setSpeaking(true);
    if (ev.type === "end") setSpeaking(false);
  }), []);
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setDrawer(null); stopAudio(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); input.current?.focus(); }
    };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, []);
  useEffect(() => { if (view === "chat") scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: quiet ? "instant" : "smooth" }); }, [replies, busy, view, quiet]);
  useEffect(() => () => { abort.current?.abort(); stopListen.current?.(); stopSpeaking(); audio.current?.pause(); void audioContext.current?.close(); }, []);

  function stopAudio() {
    speechEpoch.current++; audio.current?.pause();
    if (audio.current) { URL.revokeObjectURL(audio.current.src); audio.current = null; }
    stopSpeaking(); setSpeaking(false); setVoiceLoading(false);
    void audioContext.current?.close().catch(() => {}); audioContext.current = null; analyser.current = null;
  }
  async function readAloud(text: string) {
    stopAudio(); const epoch = speechEpoch.current;
    if (!natural) {
      if (!speak(text, { rate: tone === "fokus" ? 1.02 : 1.12 })) setError("Ingen svensk enhetsröst är tillgänglig. Välj naturlig röst.");
      return;
    }
    setVoiceLoading(true);
    try {
      const ctx = new AudioContext(); audioContext.current = ctx; await ctx.resume();
      const r = await fetch(BRIDGE + "/api/voice", { method: "POST",
        headers: { "Content-Type": "application/json", "x-jarvis-key": getKey() },
        body: JSON.stringify({ text: text.slice(0, 1400), personality: tone }), signal: AbortSignal.timeout(90000) });
      if (!r.ok) throw new Error("Naturlig röst kunde inte skapas. Välj enhetsröst i inställningarna.");
      const blob = await r.blob();
      if (epoch !== speechEpoch.current) { void ctx.close(); return; }
      const a = new Audio(URL.createObjectURL(blob)); audio.current = a;
      const source = ctx.createMediaElementSource(a), node = ctx.createAnalyser();
      node.fftSize = 256; source.connect(node); node.connect(ctx.destination); analyser.current = node;
      a.onended = () => { if (epoch === speechEpoch.current) stopAudio(); };
      a.onerror = () => { stopAudio(); setError("Ljudet kunde inte spelas. Prova enhetsröst."); };
      await a.play(); setSpeaking(true);
    } catch (e) { if (epoch === speechEpoch.current) { stopAudio(); setError((e as Error).message); } }
    finally { if (epoch === speechEpoch.current) setVoiceLoading(false); }
  }
  function toggleListen() {
    if (listening) { stopListen.current?.(); setListening(false); return; }
    stopAudio();
    const stop = listen(); stopListen.current = stop;
    if (stop) setListening(true); else setError("Röstinmatning stöds inte här. Skriv din fråga i stället.");
  }
  async function login(e: React.FormEvent) {
    e.preventDefault(); setLoading(true); setError(""); setKey(password.trim());
    try { await call("health"); keyState(password.trim()); setPassword(""); }
    catch { setKey(""); setError("Nyckeln godkändes inte eller Jarvis svarar inte. Försök igen."); }
    finally { setLoading(false); }
  }
  async function send() {
    if (!msg.trim() || busy || !key) return;
    stopAudio(); stopListen.current?.(); setListening(false);
    const text = msg.trim(); setBusy(true); setError(""); setView("chat");
    const ctl = new AbortController(); abort.current = ctl;
    try {
      const result = await bridge<Omit<Reply, "id" | "question">>("/api/chat", {
        message: text, selected, personality: tone,
        history: replies.slice(-5).flatMap(r => [{ role: "user", content: r.question }, { role: "assistant", content: r.answer }]),
      }, ctl.signal);
      setReplies(r => [...r, { ...result, question: text, id: crypto.randomUUID() }]); setMsg("");
      if (autoRead) void readAloud(result.answer);
    } catch (e) { setError(ctl.signal.aborted ? "Svaret avbröts i vyn. En redan påbörjad läsning kan slutföras på servern." : (e as Error).message); }
    finally { setBusy(false); abort.current = null; }
  }
  async function refreshCatalog() {
    setLoading(true); setError("");
    try { setCatalog(await bridge<Catalog>("/api/catalog/refresh", {})); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }
  function toggleSource(id: string) { setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]); }
  const orbMode = speaking ? "speaking" : listening ? "listening" : busy || voiceLoading ? "thinking" : "idle";
  const orbText = speaking ? "Jag pratar." : listening ? "Jag lyssnar." : busy ? "Jag arbetar med din fråga." : voiceLoading ? "Jag förbereder rösten." : "Redo när du är.";
  const traces = replies.flatMap(r => r.trace.map(t => ({ ...t, at: r.at }))).reverse();

  return <div className={`app-shell ${focus ? "focus-mode" : ""}`}>
    <a className="skip-link" href="#main">Till innehållet</a>
    <aside className="sidebar">
      <div className="brand"><Logo/><div>JARVIS<span>RICKY / PERSONAL OS</span></div></div>
      <div className="workspace-label">DITT KONTROLLRUM</div>
      <nav aria-label="Huvudnavigation">
        {([[ "home", Radio, "Kommandocentral" ], ["chat", Command, "Dialog"], ["memory", Brain, "Minne & underlag"], ["activity", Activity, "Aktivitetslogg"]] as const).map(([id, Icon, label]) =>
          <button data-testid={`nav-${id}`} className={view === id ? "nav-item active" : "nav-item"} onClick={() => setView(id)} key={id}><Icon size={18}/>{label}{view === id && <span className="nav-dot"/>}</button>)}
      </nav>
      <div className="workspace-label">FÖRMÅGOR</div>
      <button className="nav-item" data-testid="nav-connections" onClick={() => setDrawer("connections")}><Network size={18}/>Anslutningar <span className="count">{catalog?.connectors.length ?? "·"}</span></button>
      <button className="nav-item" data-testid="nav-skills" onClick={() => setDrawer("skills")}><Layers size={18}/>Arbetslägen</button>
      <div className="sidebar-bottom">
        <div className="safe-card"><ShieldCheck size={18}/><div>Skyddat läsläge<small>Inga externa utskick</small></div><LockKeyhole size={14}/></div>
        <button className="profile" onClick={() => setDrawer("settings")} data-testid="button-profile"><span className="avatar">R</span><span>Ricky<small>Din privata arbetsyta</small></span><SlidersHorizontal size={17}/></button>
      </div>
    </aside>

    <header className="topbar">
      <div className="breadcrumb"><span className="mobile-logo"><Logo/></span><span>JARVIS</span><span>/</span><b>{view === "home" ? "Kommandocentral" : view === "chat" ? "Dialog" : view === "memory" ? "Minne & underlag" : "Aktivitetslogg"}</b></div>
      <div className="top-controls"><span className="session-badge"><i className={key ? "dot green" : "dot"}/>{key ? "Privat session" : "Låst session"}</span><span className="clock">{clock.toLocaleTimeString("sv-SE", {hour:"2-digit",minute:"2-digit"})} <small>STOCKHOLM</small></span>
        <button className="icon-btn" data-testid="button-theme" onClick={() => setDark(v => !v)} title="Byt färgtema" aria-label="Byt färgtema">{dark ? <Sun size={18}/> : <Moon size={18}/>}</button>
        <button className="icon-btn" data-testid="button-focus" onClick={() => setFocus(v => !v)} title="Fokusläge" aria-label="Fokusläge" aria-pressed={focus}><PanelLeftClose size={18}/></button>
      </div>
    </header>

    <main id="main" className="main-area">
      <div className="page-heading"><div><div className="eyebrow">INTELLIGENS. NÄRVARO. KONTROLL.</div><h1>{view === "home" ? "Ditt nästa drag. Jag är med." : view === "chat" ? "Vi tar det härifrån." : view === "memory" ? "Ett minne med källor." : "Se vad som faktiskt händer."}</h1></div><button className="text-btn" onClick={() => setDrawer("settings")}><SlidersHorizontal size={16}/><span>Anpassa Jarvis</span></button></div>

      <div className="content-layout">
        <div className="main-column">
          <div className="workspace" ref={scroll}>
            {(view === "home" || !key) && <section className="presence-stage" aria-label="Jarvis närvaro">
              <div className="stage-top"><span><i className="dot green"/> JARVIS / NÄRVARO</span><span className="subtle">01 / CORE</span></div>
              <Presence mode={orbMode} quiet={quiet} analyser={analyser} />
              <div className="orbit-label label-left"><span>KONTEXT</span><b>{selected.length ? `${selected.length} valda källor` : "Du väljer åtkomst"}</b></div>
              <div className="orbit-label label-right"><span>UTTRYCK</span><b>{toneNames[tone]}</b></div>
              <div className="presence-copy"><div className="eyebrow">{key ? "VI ÄR IGÅNG" : "DIN PRIVATA AI-PARTNER"}</div><h2>{orbText}</h2><p>Från en tanke till ett tydligt nästa steg.</p></div>
              <div className="presence-actions"><button onClick={() => key ? void readAloud("Hej Ricky. Jag är här. Vi tar det viktiga först, och lämnar krånglet åt mig. Vad börjar vi med?") : input.current?.focus()} disabled={voiceLoading || !key} className="round-btn" aria-label="Prova Jarvis röst" data-testid="button-voice-demo"><AudioLines size={20}/></button><button onClick={() => { setView("chat"); input.current?.focus(); }} className="round-btn" aria-label="Öppna dialog" data-testid="button-open-chat"><Command size={20}/></button></div>
              <div className="stage-bottom"><span>UTTRYCKSFULL AI · INTE EGNA KÄNSLOR</span><span>DU HAR SISTA ORDET <ShieldCheck size={13}/></span></div>
            </section>}
            {key && view === "chat" && <section className="conversation" aria-label="Dialog med Jarvis">
              {!replies.length && <div className="empty-dialog"><Presence mode={orbMode} quiet={quiet} analyser={analyser}/><h2>En tanke räcker.</h2><p>Jarvis-minnet ingår. Välj extra läskällor i skrivfältet.</p><small>Samtalet stannar i den öppna fliken.</small></div>}
              {replies.map(r => <article className="exchange" key={r.id}><div className="user-message">{r.question}</div><div className="reply-author"><Logo/><b>Jarvis</b><span>{time(r.at)}</span></div><RichText text={r.answer}/>{r.trace.length > 0 && <details className="trace"><summary><Network size={14}/>{r.trace.length} lässteg · visa insyn</summary>{r.trace.map((t,i) => <div key={i}><b>{connectorName(t.source)}</b><span>{t.tool} · {t.status}{t.truncated ? " · förkortat resultat" : ""}</span></div>)}</details>}<div className="reply-footer"><button onClick={() => void readAloud(r.answer)} className="text-btn"><Volume2 size={15}/>Läs upp</button><span>{r.latency_ms ? `${(r.latency_ms/1000).toFixed(1)} s` : ""} · kostnad ej mätt</span></div></article>)}
              {busy && <div className="thinking-message" role="status"><span className="thinking-dots"><i/><i/><i/></span><span>Jarvis arbetar med sitt minne och dina valda läskällor.</span></div>}
            </section>}
            {key && view === "memory" && <section className="data-page"><div className="section-title"><Brain size={20}/><h2>Befintligt Jarvis-minne</h2><span>{state?.memory_chunks ?? "–"} poster</span></div><p className="muted">Hämtat från Supabase. Detta är inte automatiskt samma minne som hela din Computer-historik.</p>{state?.episodes.length ? state.episodes.map((e,i) => <article className="data-row" key={i}><small>{time(e.started_at)} · {e.episode_type}</small><h3>{e.title}</h3><p>{e.summary || "Ingen sammanfattning registrerad."}</p></article>) : <p>Inga episoder kunde visas. Uppdatera underlaget för att försöka igen.</p>}</section>}
            {key && view === "activity" && <section className="data-page"><div className="section-title"><Activity size={20}/><h2>Verifierbara lässteg</h2><button className="text-btn" onClick={refresh}><RefreshCw size={15}/>Uppdatera</button></div><p className="muted">Den här sessionens läsningar, följt av registrerade backendhändelser. Ingen bakgrundskörning startas här.</p>{traces.length ? traces.map((t,i) => <article className="activity-row" key={i}><span className="dot green"/><div><b>{connectorName(t.source)}</b><p>{t.tool} · {t.status}</p></div><time>{time(t.at)}</time></article>) : <div className="empty-note">Ingen anslutning har lästs av den här dialogen ännu.</div>}<h3>Backendens senaste händelser</h3>{state?.events.latest.map((e,i) => <article className="activity-row" key={i}><Circle size={12}/><div><b>{e.event_type}</b><p>{e.source}</p></div><time>{time(e.occurred_at)}</time></article>)}</section>}
          </div>
          {!key ? <form className="login-dock" onSubmit={login}><Fingerprint size={25}/><div><label htmlFor="jarvis-key">Lås upp ditt kontrollrum</label><small>Din befintliga Jarvis-nyckel. Endast i flikens minne.</small></div><input id="jarvis-key" data-testid="input-key" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Jarvis-nyckel" autoComplete="off" required/><button className="primary-btn" disabled={loading}>{loading ? "Kontrollerar…" : "Lås upp"}<ArrowUpRight size={16}/></button></form>
          : <div className="command-dock">
            <div className="prompt-suggestions">{["Vad ska vi prioritera?", "Kontrollera Jarvis-status", "Hitta ett underlag"].map((s,i) => <button key={s} onClick={() => {setMsg(i === 1 ? "Kontrollera mitt Jarvis Supabase-projekts status." : s); if (i === 1) setSelected(["supabase"]); if (i === 2) setSelected(["files"]); input.current?.focus(); }}><Sparkles size={13}/>{s}</button>)}</div>
            <div className="composer">
              {selected.length > 0 && <div className="selected-sources">{selected.slice(0,4).map(s => <button key={s} onClick={() => toggleSource(s)}>{connectorName(s)}<X size={12}/></button>)}{selected.length > 4 && <button onClick={() => setDrawer("connections")}>+{selected.length - 4} till</button>}</div>}
              <textarea data-testid="input-message" ref={input} value={msg} onChange={e => setMsg(e.target.value)} onKeyDown={e => {if(e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {e.preventDefault(); void send();}}} rows={2} maxLength={4000} placeholder="Vad vill du ta vidare, Ricky?" aria-label="Skriv till Jarvis"/>
              <div className="composer-toolbar"><div className="composer-tools"><button data-testid="button-connections" onClick={() => setDrawer("connections")}><Network size={16}/><span>Anslutningar</span><span className="tiny-count">{selected.length}</span></button><button data-testid="button-skills" onClick={() => setDrawer("skills")}><Layers size={16}/><span>Arbetsläge</span></button><button className="tone-shortcut" onClick={() => setDrawer("settings")}><AudioLines size={16}/>{toneNames[tone]}<ChevronDown size={12}/></button></div><div className="send-tools">{(speaking || voiceLoading) && <button className="icon-btn" onClick={stopAudio} aria-label="Stoppa rösten"><Square size={16}/></button>}<button data-testid="button-mic" className={`icon-btn ${listening ? "listening" : ""}`} onClick={toggleListen} aria-label={listening ? "Stoppa mikrofon" : "Diktera fråga"} disabled={!listenSupported} title={listenSupported ? "Diktera, granska, skicka" : "Mikrofon stöds inte här"}><Mic size={18}/></button>{busy ? <button className="send-btn" onClick={() => abort.current?.abort()} aria-label="Avbryt svar" data-testid="button-cancel"><Square size={17}/></button> : <button className="send-btn" disabled={!msg.trim() || !BRIDGE} onClick={() => void send()} aria-label="Skicka till Jarvis" data-testid="button-send"><ArrowUp size={20}/></button>}</div></div>
            </div>
            <div className="composer-foot"><span><ShieldCheck size={12}/>Läsning & utkast. Utskick låsta.</span><span>Enter för dialog · Shift Enter för ny rad</span></div>
          </div>}
          {error && <div className="inline-error" role="alert">{error}<button aria-label="Stäng felmeddelande" onClick={() => setError("")}><X size={16}/></button></div>}
        </div>

        <aside className="inspector">
          <div className="inspector-heading"><div><span className="eyebrow">NU</span><h2>Drift & kontroll</h2></div><button className="icon-btn" onClick={refresh} disabled={loading || !key} aria-label="Uppdatera underlag" data-testid="button-refresh"><RefreshCw size={16} className={loading ? "spin" : ""}/></button></div>
          <section className="status-section"><div className="metric-title"><Database size={16}/><span>Datakärnan</span><span className={`dot ${state && !state.errors.length ? "green" : "amber"}`}/></div><strong>{!key ? "Väntar på inloggning" : state ? "Underlag hämtat" : "Ansluter…"}</strong><p>{state ? `Supabase · uppdaterad ${time(state.generated_at)}` : "Din befintliga datakälla bevaras."}</p></section>
          <section className="status-section"><div className="metric-title"><Network size={16}/><span>Anslutningar</span></div><div className="big-number">{catalog?.connectors.filter(c => c.status === "CONNECTED").length ?? "–"}<small>anslutna konton</small></div><p>{available.length ? `${available.length} valbara läsvägar. Funktion provas vid användning.` : "Katalogen öppnas efter inloggning."}</p><button onClick={() => setDrawer("connections")} className="text-btn">Hantera åtkomst<ArrowUpRight size={14}/></button></section>
          <section className="status-section"><div className="metric-title"><ShieldCheck size={16}/><span>Handlingsutrymme</span><LockKeyhole size={14}/></div><div className="permission-row"><span>Läsning & analys</span><b>Tillåtet</b></div><div className="permission-row"><span>Mejl & meddelanden</span><span>Låst</span></div><div className="permission-row"><span>Betalning & publicering</span><span>Låst</span></div></section>
          <section className="runtime-note"><span className="eyebrow">ATT SKILJA PÅ</span><h3>Vyn är inte hela systemet.</h3><p>Dialogen körs i en privat Computer-brygga. Prime-automationer är fortsatt pausade. Windows-genvägen väntar på en online-dator.</p></section>
          <div className="inspector-footer"><i className="dot"/><span>Ingen hårddisk ansluten</span></div>
        </aside>
      </div>
    </main>
    {key && <button className="jarvis-bubble" data-testid="button-bubble" onClick={() => {setView(view === "chat" ? "home" : "chat"); input.current?.focus();}} aria-label="Växla Jarvis-bubblan"><Presence mode={orbMode} quiet={quiet} analyser={analyser} mini/><span>{busy ? "Arbetar" : speaking ? "Talar" : "Jarvis"}</span></button>}
    <nav className="mobile-nav">{([[ "home", Radio, "Central" ], ["chat", Command, "Dialog"], ["memory", Brain, "Minne"], ["activity", Activity, "Insyn"]] as const).map(([id,Icon,label]) => <button key={id} onClick={() => setView(id)} className={view === id ? "active" : ""}><Icon size={18}/><span>{label}</span></button>)}</nav>

    {drawer && <div className="modal-backdrop" onClick={e => {if(e.target === e.currentTarget) setDrawer(null);}}>
      <section className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" onKeyDown={e => {
        if(e.key !== "Tab") return;
        const nodes = [...e.currentTarget.querySelectorAll<HTMLElement>("button:not([disabled]), input, select, a[href]")];
        if (e.shiftKey && document.activeElement === nodes[0]) {e.preventDefault(); nodes.at(-1)?.focus();}
        else if (!e.shiftKey && document.activeElement === nodes.at(-1)) {e.preventDefault(); nodes[0]?.focus();}
      }}>
        <header><div><span className="eyebrow">{drawer === "connections" ? "DU VÄLJER KÄLLORNA" : drawer === "skills" ? "EN TYDLIG RIKTNING" : "PERSONLIGHET & KONTROLL"}</span><h2 id="drawer-title">{drawer === "connections" ? "Jarvis anslutningar" : drawer === "skills" ? "Välj ett arbetsläge" : "Gör Jarvis till din."}</h2></div><button autoFocus className="icon-btn" onClick={() => setDrawer(null)} aria-label="Stäng panel"><X size={21}/></button></header>
        <div className="drawer-body">
          {drawer === "connections" && <><p>Välj källor här eller i skrivfältet. Valet ger enbart läsbehörighet för nästa fråga, aldrig tillåtelse till utskick.</p><div className="search-field"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Sök bland dina anslutningar" aria-label="Sök anslutning" data-testid="input-search-connectors"/></div><div className="drawer-actions"><button className="text-btn" onClick={() => setSelected(available.map(c=>c.source_id))} disabled={!key}>Välj alla läsbara</button><button className="text-btn" onClick={()=>setSelected([])}>Rensa val</button><button className="text-btn" onClick={refreshCatalog} disabled={loading || !key}><RefreshCw size={14}/>Kontrollera nu</button></div><small className="muted">Kontroll: {time(catalog?.at)} · ansluten är inte samma sak som funktionstestad.</small><div className="connector-grid">{catalog?.connectors.filter(c=>c.name.toLowerCase().includes(search.toLowerCase())).map(c => {
            const ready = c.status === "CONNECTED" && c.read_tools.length > 0;
            return <button className={`connector-option ${selected.includes(c.source_id) ? "selected" : ""}`} key={c.source_id} disabled={!ready} onClick={()=>toggleSource(c.source_id)} data-testid={`source-${c.source_id}`}><div className="connector-monogram">{c.name.slice(0,2).toUpperCase()}</div><div><b>{c.name}</b><small>{ready ? "Läsadapter · provas vid användning" : c.status !== "CONNECTED" ? "Anslutning behöver verifieras" : c.note || "Adapter återstår"}</small></div><span className="checkbox">{selected.includes(c.source_id) ? <Check size={14}/> : !ready ? <LockKeyhole size={12}/> : null}</span></button>;
          })}</div>{!catalog && <div className="empty-note">Logga in för att hämta dina anslutningar.</div>}<p className="muted">Dropbox, OneDrive och Google Drive söker via den gemensamma filanslutningen och kan ge träffar från flera filkällor. Frysta tjänster återaktiveras inte av ”välj alla”.</p></>}
          {drawer === "skills" && <><p>De här genvägarna förbereder din fråga. De importerar inte Computer-skills eller aktiverar automationer i webbappen.</p><div className="mode-list">{WORK_MODES.map(([name,desc,prompt],i)=><button key={name} onClick={()=>{setMsg(prompt); if(i===4) setSelected(["supabase"]); setDrawer(null); input.current?.focus();}}><span className="mode-index">{String(i+1).padStart(2,"0")}</span><div><b>{name}</b><small>{desc}</small></div><ArrowUpRight size={17}/></button>)}</div><a className="external-link" href="https://www.perplexity.ai/computer/skills" target="_blank" rel="noreferrer">Öppna hela ditt skillbibliotek i Computer<ArrowUpRight size={16}/></a></>}
          {drawer === "settings" && <><h3>En varm röst. Mer liv.</h3><p>Tonläget är ett uttryckssätt, inte egna känslor. Varm + är snabbare, mjuk och lekfull; Fokus passar allvarliga frågor.</p><div className="tone-options">{(["varm","gnista","fokus"] as const).map(t=><button key={t} className={tone===t ? "selected" : ""} onClick={()=>setTone(t)}><AudioLines size={18}/><b>{toneNames[t]}</b>{tone===t&&<Check size={15}/>}</button>)}</div><label className="toggle-row">Naturlig genererad röst<input type="checkbox" checked={natural} onChange={e=>setNatural(e.target.checked)}/></label><small className="muted">Genereras vid uppspelning. Kan ta en stund och använda modellkrediter. Av = svensk enhetsröst.</small><label className="toggle-row">Läs upp nya svar<input type="checkbox" checked={autoRead} onChange={e=>setAutoRead(e.target.checked)}/></label><label className="toggle-row">Lugnare rörelser<input type="checkbox" checked={quiet} onChange={e=>setQuiet(e.target.checked)}/></label><button className="primary-btn" disabled={!key || voiceLoading} onClick={()=>void readAloud("Hej Ricky. Jag håller koll på detaljerna. Du väljer riktningen. Ska vi göra något riktigt bra av den här dagen?")}><Volume2 size={17}/>{voiceLoading ? "Förbereder rösten…" : "Prova rösten"}</button>{(speaking||voiceLoading)&&<button className="text-btn" onClick={stopAudio}><Square size={16}/>Stoppa</button>}<div className="settings-note"><h3>Din kontroll</h3><p>Inga lösenord sparas i webbläsarlagring. Nya samtal finns i fliken och försvinner när den stängs. Ingen mätt kostnad visas som noll.</p><p>Utskick, betalningar och publicering är serverlåsta. Ingen knapp kan avaktivera spärren.</p></div>{key&&<button className="text-btn danger" onClick={()=>{stopAudio();abort.current?.abort();setKey("");keyState("");setState(null);setCatalog(null);setReplies([]);setSelected([]);setDrawer(null);}}><LogOut size={17}/>Logga ut & töm sessionen</button>}</>}
        </div><footer><span><LockKeyhole size={13}/>Extern påverkan är låst</span><button className="primary-btn" onClick={()=>setDrawer(null)}>Klart<Check size={16}/></button></footer>
      </section>
    </div>}
  </div>;
}
