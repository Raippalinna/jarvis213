// JARVIS-kärnan: fysikmodell + canvas-rendering.
//
// Fysik (allt körs i realtid, ingen förinspelad animation):
//  • Ytan är en sluten sträng av N noder. Varje nod har radiell förskjutning x och hastighet v.
//    Kraft = -k·x (återställande fjäder)  - c·v (dämpning)  + kn·(x[i-1] + x[i+1] - 2x[i]) (spänning mot grannar)
//    Grannkopplingen ger vågutbredning längs ytan, som en membran/sträng. Semi-implicit Euler, fasta delsteg.
//  • Röst/tanke matar in energi som en drivkraft (bruskälla + impulser per stavelse). Utan energi klingar ytan
//    av exponentiellt enligt dämpningen – kärnan "andas" bara svagt i vila.
//  • Partiklarna följer Newtons gravitation mot centrum (F = G/r², begränsad nära r→0), med begynnelsehastighet
//    v = sqrt(G/r) för cirkulära banor (Kepler). Dämpning och en mjuk repulsion från ytan hindrar kollaps.
//    När Jarvis talar får partiklarna radiella impulser och faller sedan tillbaka i bana.
//  • Ringarna roterar med ω = sqrt(G/r³) (Keplers tredje lag) – yttre ringar långsammare än inre.
//  • Pekaren (mus/finger) skjuter ytan med en 1/d²-kraft.

export type OrbMode = "offline" | "idle" | "thinking" | "speaking" | "listening";

const TAU = Math.PI * 2;

export class OrbPhysics {
  readonly N = 128;
  x = new Float32Array(this.N);
  v = new Float32Array(this.N);
  private drive = new Float32Array(this.N);
  // Partiklar
  readonly M = 110;
  px = new Float32Array(this.M); py = new Float32Array(this.M);
  pvx = new Float32Array(this.M); pvy = new Float32Array(this.M);
  psize = new Float32Array(this.M);
  // Parametrar (enheter: radie = 1)
  k = 38;      // fjäderkonstant mot viloläge
  c = 3.2;     // dämpning
  kn = 220;    // grannspänning (vågutbredning)
  G = 1.6;     // gravitationskonstant för partiklar
  mode: OrbMode = "idle";
  level = 0;   // rösteffekt 0..1 (extern)
  energy = 0;  // filtrerad energinivå för render
  t = 0;
  pointer: { x: number; y: number; active: boolean } = { x: 0, y: 0, active: false };
  private phase = new Float32Array(this.N);
  private seed: number[] = [];

  constructor() {
    for (let i = 0; i < this.N; i++) this.phase[i] = Math.random() * TAU;
    for (let j = 0; j < 6; j++) this.seed.push(0.7 + Math.random() * 2.3);
    for (let i = 0; i < this.M; i++) this.spawnParticle(i, true);
  }

  private spawnParticle(i: number, init = false) {
    const r = 1.35 + Math.random() * 1.6;
    const a = Math.random() * TAU;
    this.px[i] = Math.cos(a) * r; this.py[i] = Math.sin(a) * r;
    const vOrb = Math.sqrt(this.G / r) * (init ? 1 : 0.9 + Math.random() * 0.2);
    const dir = Math.random() < 0.85 ? 1 : -1; // några få retrograda banor
    this.pvx[i] = -Math.sin(a) * vOrb * dir; this.pvy[i] = Math.cos(a) * vOrb * dir;
    this.psize[i] = 0.6 + Math.random() * 1.4;
  }

  /** Impuls på ytan runt vinkel a (radianer), styrka s (enheter av hastighet). */
  kick(a: number, s: number, width = 0.35) {
    for (let i = 0; i < this.N; i++) {
      const ai = (i / this.N) * TAU;
      let d = Math.abs(((ai - a + Math.PI) % TAU + TAU) % TAU - Math.PI);
      const w = Math.exp(-(d * d) / (2 * width * width));
      this.v[i] += s * w;
    }
  }

  /** Stavelseimpuls: slumpad riktning, styrka från röstnivå. */
  syllable(strength = 1) {
    this.kick(Math.random() * TAU, (0.9 + Math.random() * 0.8) * strength, 0.5);
    // ge partiklarna en radiell knuff (utbrott)
    for (let i = 0; i < this.M; i++) {
      if (Math.random() < 0.25 * strength) {
        const r = Math.hypot(this.px[i], this.py[i]) || 1;
        const s = 0.35 * strength * (0.5 + Math.random());
        this.pvx[i] += (this.px[i] / r) * s; this.pvy[i] += (this.py[i] / r) * s;
      }
    }
  }

  private noise(i: number, t: number) {
    // billig kvasi-brusfunktion: summa av sinusar med inkommensurabla frekvenser
    const a = (i / this.N) * TAU;
    let n = 0;
    for (let j = 0; j < this.seed.length; j++) n += Math.sin(a * (j + 1) * 1.3 + t * this.seed[j] * (0.6 + j * 0.15) + this.phase[i]) / (j + 1.5);
    return n / 2.2;
  }

  step(dt: number) {
    const sub = 4, h = dt / sub;
    const targetE = this.mode === "offline" ? 0.05 : this.mode === "idle" ? 0.18 : this.mode === "thinking" ? 0.6 : this.mode === "listening" ? 0.4 : 0.35 + 0.65 * this.level;
    this.energy += (targetE - this.energy) * Math.min(1, dt * 3.5);
    // dämpning skiljer sig med läge: tänkande = "vibrerande" ytan, tal = kraftig drivning
    const c = this.mode === "thinking" ? 2.2 : this.c;
    for (let s = 0; s < sub; s++) {
      this.t += h;
      const drivAmp = this.mode === "offline" ? 0.4 : this.mode === "thinking" ? 9 : this.mode === "speaking" ? 6 + 26 * this.level : this.mode === "listening" ? 4 : 1.6;
      const speed = this.mode === "thinking" ? 3.2 : 1;
      for (let i = 0; i < this.N; i++) this.drive[i] = this.noise(i, this.t * speed) * drivAmp;
      // pekarkraft
      const pa = this.pointer.active;
      for (let i = 0; i < this.N; i++) {
        const l = (i + this.N - 1) % this.N, r = (i + 1) % this.N;
        let F = -this.k * this.x[i] - c * this.v[i] + this.kn * (this.x[l] + this.x[r] - 2 * this.x[i]) + this.drive[i];
        if (pa) {
          const a = (i / this.N) * TAU, R = 1 + this.x[i];
          const nx = Math.cos(a) * R, ny = Math.sin(a) * R;
          const dx = nx - this.pointer.x, dy = ny - this.pointer.y;
          const d2 = dx * dx + dy * dy + 0.02;
          // radiell komposant av 1/d²-repulsion
          const fr = (dx * Math.cos(a) + dy * Math.sin(a)) / Math.sqrt(d2) * (0.9 / d2);
          F += Math.max(-40, Math.min(40, fr));
        }
        this.v[i] += F * h;
      }
      for (let i = 0; i < this.N; i++) { this.x[i] += this.v[i] * h; if (this.x[i] < -0.55) { this.x[i] = -0.55; this.v[i] *= -0.3; } }
      // partiklar
      const G = this.G * (this.mode === "thinking" ? 1.25 : 1);
      for (let i = 0; i < this.M; i++) {
        const x = this.px[i], y = this.py[i];
        const r2 = x * x + y * y, r = Math.sqrt(r2) || 1e-3;
        const g = -G / Math.max(r2, 0.6) / r; // gravitation, begränsad nära centrum
        let ax = g * x, ay = g * y;
        // mjuk repulsion från ytan (så de inte faller in i kärnan)
        const surf = 1.12;
        if (r < surf) { const p = (surf - r) * 14; ax += (x / r) * p; ay += (y / r) * p; }
        // svag dämpning håller banorna stabila efter impulser
        ax -= this.pvx[i] * 0.06; ay -= this.pvy[i] * 0.06;
        this.pvx[i] += ax * h; this.pvy[i] += ay * h;
        this.px[i] += this.pvx[i] * h; this.py[i] += this.pvy[i] * h;
        if (r > 4.5) this.spawnParticle(i);
      }
    }
  }
}

export interface Palette { a: string; b: string; glow: string; rgb: [number, number, number] }
export const PALETTES: Record<OrbMode, Palette> = {
  offline:   { a: "#ff6b8b", b: "#7a1f3a", glow: "rgba(255,107,139,", rgb: [255, 107, 139] },
  idle:      { a: "#5ee7ff", b: "#2a5cff", glow: "rgba(94,231,255,",  rgb: [94, 231, 255] },
  thinking:  { a: "#b18cff", b: "#5b2bd6", glow: "rgba(139,92,246,",  rgb: [160, 120, 255] },
  speaking:  { a: "#7ff3ff", b: "#3b7bff", glow: "rgba(120,240,255,", rgb: [120, 240, 255] },
  listening: { a: "#a3ff6b", b: "#1f9d6b", glow: "rgba(163,255,107,", rgb: [163, 255, 107] },
};

export function render(ctx: CanvasRenderingContext2D, phys: OrbPhysics, w: number, h: number, pal: Palette, mix: Palette | null, mixT: number) {
  const cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.26;
  const E = phys.energy;
  ctx.clearRect(0, 0, w, h);
  const col = (p: Palette, alpha: number) => `${p.glow}${alpha})`;
  const lerpRgb = (a: [number, number, number], b: [number, number, number], t: number) => a.map((v, i) => Math.round(v + (b[i] - v) * t)) as [number, number, number];
  const rgb = mix ? lerpRgb(pal.rgb, mix.rgb, mixT) : pal.rgb;
  const rgba = (a: number) => `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`;

  // 1. Yttre glöd (storlek följer energin)
  const g0 = ctx.createRadialGradient(cx, cy, R * 0.4, cx, cy, R * (2.2 + E * 1.2));
  g0.addColorStop(0, rgba(0.28 + E * 0.25)); g0.addColorStop(0.5, rgba(0.07)); g0.addColorStop(1, rgba(0));
  ctx.fillStyle = g0; ctx.fillRect(0, 0, w, h);

  // 2. Kepler-ringar
  ctx.save(); ctx.translate(cx, cy);
  const rings = [1.55, 2.05, 2.7];
  rings.forEach((rr, i) => {
    const omega = Math.sqrt(phys.G / (rr * rr * rr)) * 0.9;
    const ang = phys.t * omega * (i % 2 ? -1 : 1) + i;
    ctx.save(); ctx.rotate(ang); ctx.scale(1, 0.32 + i * 0.16);
    ctx.beginPath(); ctx.ellipse(0, 0, R * rr, R * rr, 0, 0, TAU);
    ctx.setLineDash(i === 1 ? [3, 9] : [14, 10]); ctx.lineDashOffset = -phys.t * 30 * (i + 1);
    ctx.strokeStyle = rgba(0.16 + E * 0.15); ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();
  });
  ctx.restore();

  // 3. Partiklar (med kort svans i rörelseriktningen)
  for (let i = 0; i < phys.M; i++) {
    const x = cx + phys.px[i] * R, y = cy + phys.py[i] * R;
    const sp = Math.hypot(phys.pvx[i], phys.pvy[i]);
    const a = Math.min(0.9, 0.25 + sp * 0.35 + E * 0.3);
    ctx.strokeStyle = rgba(a * 0.5); ctx.lineWidth = phys.psize[i] * 0.8;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - phys.pvx[i] * R * 0.06, y - phys.pvy[i] * R * 0.06); ctx.stroke();
    ctx.fillStyle = rgba(a); ctx.beginPath(); ctx.arc(x, y, phys.psize[i] * 0.9, 0, TAU); ctx.fill();
  }

  // 4. Kärnans yta (mjuk kurva genom noderna)
  const pts: [number, number][] = [];
  for (let i = 0; i < phys.N; i++) {
    const a = (i / phys.N) * TAU, r = R * (1 + phys.x[i] * 0.55);
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  const path = new Path2D();
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i], q = pts[(i + 1) % pts.length];
    const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
    if (i === 0) path.moveTo(mx, my); else path.quadraticCurveTo(p[0], p[1], mx, my);
  }
  path.closePath();
  ctx.save();
  ctx.shadowColor = rgba(0.55 + E * 0.4); ctx.shadowBlur = 18 + E * 40;
  const g1 = ctx.createRadialGradient(cx - R * 0.25, cy - R * 0.3, R * 0.1, cx, cy, R * 1.15);
  g1.addColorStop(0, "rgba(255,255,255,0.92)"); g1.addColorStop(0.18, pal.a); g1.addColorStop(0.65, pal.b); g1.addColorStop(1, "rgba(5,7,13,0.9)");
  ctx.fillStyle = g1; ctx.fill(path);
  ctx.restore();
  ctx.strokeStyle = rgba(0.75); ctx.lineWidth = 1.2; ctx.stroke(path);

  // 5. Inre plasma: två roterande ljusbågar som följer ytenergin
  ctx.save(); ctx.translate(cx, cy);
  for (let j = 0; j < 2; j++) {
    ctx.rotate(phys.t * (j ? -0.9 : 0.6));
    ctx.beginPath(); ctx.arc(0, 0, R * (0.55 + j * 0.18), 0, Math.PI * (0.6 + E * 0.9));
    ctx.strokeStyle = `rgba(255,255,255,${0.18 + E * 0.35})`; ctx.lineWidth = 1.5 + E * 2; ctx.stroke();
  }
  ctx.restore();

  // 6. Vågform-ring vid tal (amplitud = nodhastighet, dvs. ytans faktiska rörelse)
  if (phys.mode === "speaking" || phys.mode === "listening") {
    ctx.save(); ctx.translate(cx, cy);
    ctx.beginPath();
    for (let i = 0; i <= phys.N; i++) {
      const k = i % phys.N, a = (k / phys.N) * TAU, r = R * 1.28 + Math.abs(phys.v[k]) * R * 0.12;
      i === 0 ? ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r) : ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    ctx.strokeStyle = col(pal, 0.35 + E * 0.4); ctx.lineWidth = 1; ctx.stroke();
    ctx.restore();
  }
}
