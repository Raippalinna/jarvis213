import { useEffect, useRef } from "react";
import { OrbPhysics, PALETTES, render, type OrbMode } from "./orb";
import { onVoice } from "./voice";

/**
 * Jarvis-kärnan som canvas. `mode` sätter grundtillstånd; rösthändelser (tal/lyssning) tar över
 * automatiskt medan de pågår. Reagerar på pekare/finger (fysisk repulsion).
 */
export function JarvisOrb({ mode, size = 280, className = "", interactive = true }: { mode: OrbMode; size?: number; className?: string; interactive?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const phys = useRef<OrbPhysics | null>(null);
  const modeRef = useRef<OrbMode>(mode);
  const voiceRef = useRef<{ speaking: boolean; listening: boolean }>({ speaking: false, listening: false });
  const palRef = useRef<{ from: OrbMode; to: OrbMode; t: number }>({ from: mode, to: mode, t: 1 });

  useEffect(() => { modeRef.current = mode; }, [mode]);

  useEffect(() => {
    const unsub = onVoice((ev) => {
      const p = phys.current; if (!p) return;
      switch (ev.type) {
        case "start": voiceRef.current.speaking = true; p.level = 0.5; p.syllable(1.2); break;
        case "end": voiceRef.current.speaking = false; p.level = 0; break;
        case "level": p.level = ev.level; break;
        case "syllable": p.syllable(ev.strength); break;
        case "listen-start": voiceRef.current.listening = true; p.kick(Math.PI / 2, 1.5, 0.8); break;
        case "listen-end": voiceRef.current.listening = false; break;
        case "transcript": if (!ev.final) p.syllable(0.4); break;
      }
    });
    return unsub;
  }, []);

  useEffect(() => {
    const canvas = ref.current; if (!canvas) return;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    const p = phys.current ?? (phys.current = new OrbPhysics());
    let reduce = false;
    try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* ok */ }
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = size, h = size;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    let raf = 0, last = performance.now(), visible = true;
    const io = new IntersectionObserver((es) => { visible = es[0]?.isIntersecting ?? true; });
    io.observe(canvas);

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      if (!visible) return;
      const eff: OrbMode = voiceRef.current.speaking ? "speaking" : voiceRef.current.listening ? "listening" : modeRef.current;
      p.mode = eff;
      const pr = palRef.current;
      if (pr.to !== eff) { pr.from = pr.to; pr.to = eff; pr.t = 0; }
      pr.t = Math.min(1, pr.t + dt * 2.5);
      p.step(reduce ? dt * 0.35 : dt);
      render(ctx, p, w, h, PALETTES[pr.to], pr.t < 1 ? PALETTES[pr.from] : null, 1 - pr.t);
    };
    raf = requestAnimationFrame(frame);

    const toLocal = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      const R = Math.min(w, h) * 0.26;
      return { x: ((e.clientX - r.left) - w / 2) / R, y: ((e.clientY - r.top) - h / 2) / R };
    };
    const move = (e: PointerEvent) => { const l = toLocal(e); p.pointer = { ...l, active: true }; };
    const leave = () => { p.pointer.active = false; };
    const tap = (e: PointerEvent) => { const l = toLocal(e); p.kick(Math.atan2(l.y, l.x), 2.2, 0.6); };
    if (interactive) {
      canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerleave", leave);
      canvas.addEventListener("pointerup", leave); canvas.addEventListener("pointerdown", tap);
    }
    return () => {
      cancelAnimationFrame(raf); io.disconnect();
      canvas.removeEventListener("pointermove", move); canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("pointerup", leave); canvas.removeEventListener("pointerdown", tap);
    };
  }, [size, interactive]);

  return <canvas ref={ref} className={`block mx-auto touch-none select-none ${className}`} aria-label="Jarvis-kärnan" role="img" />;
}
