import type { ReactNode } from "react";

export function Panel({ title, right, children, className = "" }: { title?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel p-4 md:p-5 ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between mb-3">
          {title && <h2 className="text-[11px] tracking-[0.22em] uppercase text-muted font-semibold">{title}</h2>}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatusDot({ status }: { status?: string | null }) {
  const s = (status ?? "").toLowerCase();
  const color =
    /operational|healthy|active|answered|ok|true/.test(s) ? "bg-lime text-lime" :
    /connected_unverified|degraded|queued|running|paused|warn/.test(s) ? "bg-amber text-amber" :
    /disconnected|offline|failed|error|false/.test(s) ? "bg-rose text-rose" : "bg-muted text-muted";
  const pulse = /running|queued/.test(s) ? "pulse" : "";
  return <span className={`relative inline-block w-2 h-2 rounded-full ${color} ${pulse}`} aria-label={status ?? "okänd"} />;
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "cyan" | "violet" | "lime" | "amber" | "rose" | "muted" }) {
  const map = {
    cyan: "border-cyan/40 text-cyan", violet: "border-violet/50 text-violet", lime: "border-lime/40 text-lime",
    amber: "border-amber/40 text-amber", rose: "border-rose/40 text-rose", muted: "border-line text-muted",
  } as const;
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] mono ${map[tone]}`}>{children}</span>;
}

export function Ring({ value, target, label, unit, lowerIsBetter = false }: { value: number; target?: number; label: string; unit?: string; lowerIsBetter?: boolean }) {
  // lowerIsBetter: t.ex. "tid till demo" – 100 % när värdet är under målet
  const pct = !target || target <= 0 ? 0
    : lowerIsBetter ? (value <= 0 ? 0 : Math.max(0, Math.min(1, target / value)))
    : Math.max(0, Math.min(1, value / target));
  const r = 26, c = 2 * Math.PI * r;
  return (
    <div className="flex items-center gap-3">
      <svg width="68" height="68" viewBox="0 0 68 68" className="shrink-0">
        <circle cx="34" cy="34" r={r} fill="none" stroke="rgba(120,160,255,0.15)" strokeWidth="6" />
        <circle cx="34" cy="34" r={r} fill="none" stroke="url(#ringGrad)" strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`} transform="rotate(-90 34 34)" />
        <defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#5ee7ff" /><stop offset="1" stopColor="#8b5cf6" /></linearGradient></defs>
        <text x="34" y="38" textAnchor="middle" fill="#dfe9ff" fontSize="13" fontWeight="700" className="mono">{Math.round(pct * 100)}%</text>
      </svg>
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-widest text-muted truncate">{label}</div>
        <div className="mono text-lg leading-tight">{fmt(value)}<span className="text-muted text-xs ml-1">{unit}</span></div>
        {target !== undefined && <div className="text-[11px] text-muted mono">mål {fmt(target)} {unit}</div>}
      </div>
    </div>
  );
}

export function fmt(n?: number | null): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 1 }).format(n);
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "–";
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return "nu";
  if (d < 3600) return `${Math.floor(d / 60)} min`;
  if (d < 86400) return `${Math.floor(d / 3600)} h`;
  return `${Math.floor(d / 86400)} d`;
}

export function fmtTime(iso?: string | null): string {
  if (!iso) return "–";
  return new Intl.DateTimeFormat("sv-SE", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Stockholm" }).format(new Date(iso));
}

export function Spark({ values, color = "#5ee7ff" }: { values: number[]; color?: string }) {
  if (values.length < 2) return null;
  const w = 120, h = 32, max = Math.max(...values, 1), min = Math.min(...values, 0);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 4) - 2}`).join(" ");
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}><polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" /></svg>;
}

