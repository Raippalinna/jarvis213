// Röst: tal (Web Speech Synthesis) och lyssning (SpeechRecognition), svenska.
// Ingen nyckel, inget nätverk utöver webbläsarens egna röstmotor.
// Envelope-signalen (0..1) driver kärnans fysik medan Jarvis pratar.

type Listener = (ev: VoiceEvent) => void;
export type VoiceEvent =
  | { type: "start" } | { type: "end" } | { type: "level"; level: number } | { type: "syllable"; strength: number }
  | { type: "listen-start" } | { type: "listen-end" } | { type: "transcript"; text: string; final: boolean };

const listeners = new Set<Listener>();
export function onVoice(l: Listener) { listeners.add(l); return () => { listeners.delete(l); }; }
function emit(ev: VoiceEvent) { listeners.forEach((l) => l(ev)); }

export const voiceSupported = typeof window !== "undefined" && "speechSynthesis" in window;
type SR = { new(): { lang: string; continuous: boolean; interimResults: boolean; onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null; onend: (() => void) | null; onerror: (() => void) | null; start(): void; stop(): void } };
const SRCtor: SR | undefined = typeof window !== "undefined" ? ((window as unknown as { SpeechRecognition?: SR; webkitSpeechRecognition?: SR }).SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: SR }).webkitSpeechRecognition) : undefined;
export const listenSupported = Boolean(SRCtor);

let envTimer: number | null = null;
let current: SpeechSynthesisUtterance | null = null;

function pickVoice(): SpeechSynthesisVoice | null {
  const vs = speechSynthesis.getVoices();
  const sv = vs.filter((v) => /^sv/i.test(v.lang));
  // föredra "naturliga"/neurala röster där de finns
  return sv.find((v) => /natural|neural|premium|enhanced/i.test(v.name)) ?? sv.find((v) => /Google|Microsoft|Alva|Klara/i.test(v.name)) ?? sv[0] ?? vs.find((v) => /^en/i.test(v.lang)) ?? null;
}

/** Rensa markdown och tekniska rester så rösten läser naturligt. */
export function toSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " kodblock utelämnat ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "länk")
    .replace(/[*_#>|]+/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim()
    .slice(0, 2400);
}

export function stopSpeaking() {
  if (!voiceSupported) return;
  speechSynthesis.cancel();
  if (envTimer) { clearInterval(envTimer); envTimer = null; }
  if (current) { current = null; emit({ type: "end" }); }
}

/** Läser upp texten. Envelope: ~4,5 stavelser/s (svenskt taltempo) med slumpad betoning; boundary-events ger extra impulser. */
export function speak(text: string, opts: { rate?: number } = {}) {
  if (!voiceSupported) return false;
  stopSpeaking();
  const u = new SpeechSynthesisUtterance(toSpeech(text));
  const v = pickVoice();
  if (v) u.voice = v;
  u.lang = v?.lang ?? "sv-SE";
  u.rate = opts.rate ?? 1.02; u.pitch = 0.92;
  current = u;
  const t0 = performance.now();
  u.onstart = () => {
    emit({ type: "start" });
    envTimer = window.setInterval(() => {
      const t = (performance.now() - t0) / 1000;
      // två överlagrade rytmer: stavelser (~4,5 Hz) och fraser (~0,4 Hz), plus paus-sannolikhet
      const syl = 0.5 + 0.5 * Math.sin(t * 4.5 * Math.PI * 2);
      const phrase = 0.65 + 0.35 * Math.sin(t * 0.4 * Math.PI * 2 + 1);
      const pause = Math.sin(t * 0.9) > 0.92 ? 0.15 : 1;
      emit({ type: "level", level: Math.min(1, syl * phrase * pause) });
      if (syl > 0.97) emit({ type: "syllable", strength: 0.6 + Math.random() * 0.5 });
    }, 50);
  };
  u.onboundary = () => emit({ type: "syllable", strength: 1 });
  u.onend = u.onerror = () => { if (envTimer) { clearInterval(envTimer); envTimer = null; } if (current === u) { current = null; emit({ type: "end" }); } };
  speechSynthesis.speak(u);
  return true;
}

export function isSpeaking() { return current !== null; }

/** Lyssnar en gång (tills tystnad). Returnerar stop-funktion, eller null om webbläsaren saknar stöd. */
export function listen(): (() => void) | null {
  if (!SRCtor) return null;
  const r = new SRCtor();
  r.lang = "sv-SE"; r.continuous = false; r.interimResults = true;
  let stopped = false;
  r.onresult = (e) => {
    let text = ""; let final = false;
    for (let i = 0; i < e.results.length; i++) { text += e.results[i][0].transcript; if (e.results[i].isFinal) final = true; }
    emit({ type: "transcript", text, final });
  };
  r.onend = () => { if (!stopped) { stopped = true; emit({ type: "listen-end" }); } };
  r.onerror = () => { if (!stopped) { stopped = true; emit({ type: "listen-end" }); } };
  try { r.start(); emit({ type: "listen-start" }); } catch { return null; }
  return () => { if (!stopped) { stopped = true; try { r.stop(); } catch { /* ok */ } emit({ type: "listen-end" }); } };
}

// Röster laddas asynkront i vissa webbläsare
if (voiceSupported) { try { speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices(); } catch { /* ok */ } }
