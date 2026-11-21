import { useEffect, useRef, type RefObject } from "react";
type Mode = "idle" | "thinking" | "listening" | "speaking";

/** Procedural particle surface; motion reflects UI state, never fabricated telemetry. */
export function Presence({ mode, quiet, analyser, mini = false }: { mode: Mode; quiet: boolean; analyser: RefObject<AnalyserNode | null>; mini?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef(mode); state.current = mode;
  useEffect(() => {
    const el = canvas.current; if (!el) return;
    const ctx = el.getContext("2d"); if (!ctx) return;
    let raf = 0, frame = 0, visible = true;
    const reduced = quiet || matchMedia("(prefers-reduced-motion: reduce)").matches;
    const box = mini ? 80 : 500;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    el.width = box * dpr; el.height = box * dpr;
    ctx.scale(dpr, dpr);
    const radius = mini ? 24 : 124, center = box / 2, count = mini ? 270 : 1800;
    const points = Array.from({length:count}, (_,i) => {
      const y = 1 - (i/(count-1))*2, r = Math.sqrt(1-y*y), a = i * Math.PI * (3-Math.sqrt(5));
      return [Math.cos(a)*r, y, Math.sin(a)*r];
    });
    const bins = new Uint8Array(128);
    const pointer = {x:0, y:0};
    const move = (e: PointerEvent) => { const r=el.getBoundingClientRect(); pointer.x=(e.clientX-r.left)/r.width-.5; pointer.y=(e.clientY-r.top)/r.height-.5; };
    const leave = () => {pointer.x=0;pointer.y=0;};
    el.addEventListener("pointermove",move);el.addEventListener("pointerleave",leave);
    const observer = new IntersectionObserver(es=>{visible=es[0]?.isIntersecting ?? true;}); observer.observe(el);
    let last = 0;
    const render = (now:number) => {
      raf=requestAnimationFrame(render);
      if (!visible || document.hidden || now-last < (reduced ? 150 : 32)) return;
      last=now; frame+=reduced ? 0 : .016;
      const t=frame, current=state.current;
      let level=0;
      if (current==="speaking" && analyser.current) {analyser.current.getByteFrequencyData(bins); level=bins.reduce((a,b)=>a+b,0)/bins.length/255;}
      const intensity=current==="thinking" ? .065 : current==="listening" ? .04 : .018+level*.22;
      const angle=t*(current==="thinking" ? .65 : .19)+pointer.x*.25;
      const light=document.documentElement.dataset.theme==="light";
      const accent=light ? (current==="speaking" ? [132,67,37] : [28,91,103])
        : current==="listening" ? [191,225,155] : current==="speaking" ? [255,203,167] : [133,211,221];
      ctx.clearRect(0,0,box,box);
      const glow=ctx.createRadialGradient(center,center,radius*.2,center,center,radius*1.7);
      glow.addColorStop(0,`rgba(${accent},.055)`);glow.addColorStop(.6,`rgba(${accent},.025)`);glow.addColorStop(1,`rgba(${accent},0)`);
      ctx.fillStyle=glow;ctx.fillRect(0,0,box,box);
      if(!mini){
        ctx.strokeStyle=`rgba(${accent},.10)`;ctx.lineWidth=.6;
        for (let n=0;n<3;n++) {ctx.save();ctx.translate(center,center);ctx.rotate(-.3+n*.52+Math.sin(t*.2)*.05);ctx.beginPath();ctx.ellipse(0,0,radius*(1.43+n*.06),radius*(.45+n*.09),0,0,Math.PI*2);ctx.stroke();ctx.restore();}
        ctx.setLineDash([1,9]);ctx.strokeStyle=`rgba(${accent},.13)`;ctx.beginPath();ctx.arc(center,center,radius*1.73,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
      }
      const projected = points.map(([x,y,z],i)=>{
        const xr=x*Math.cos(angle)-z*Math.sin(angle), zr=x*Math.sin(angle)+z*Math.cos(angle);
        const wave=1+Math.sin(y*6+x*3+t*1.5)*Math.cos(z*5-t)*intensity;
        const yr=y*Math.cos(.2+pointer.y*.18)-zr*Math.sin(.2+pointer.y*.18);
        const depth=y*Math.sin(.2)+zr*Math.cos(.2), persp=2.9/(2.9-depth*.23);
        return {x:center+xr*radius*wave*persp,y:center+yr*radius*wave*persp,z:depth,i};
      }).sort((a,b)=>a.z-b.z);
      for(const p of projected){
        const alpha=.11+(p.z+1)*.34;
        const bright=p.z>.48 && Math.sin(p.i*.17+t*.35)>.3;
        ctx.fillStyle=bright && !light ? `rgba(228,249,243,${alpha})` : `rgba(${accent},${alpha*.82})`;
        ctx.beginPath();ctx.arc(p.x,p.y,(mini?.42:.65)+(p.z+1)*(mini?.18:.33),0,Math.PI*2);ctx.fill();
        if(!mini && p.z>.3 && p.i%6===0){ctx.strokeStyle=`rgba(${accent},.06)`;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(p.x+6,p.y+3);ctx.stroke();}
      }
    };
    raf=requestAnimationFrame(render);
    return()=>{cancelAnimationFrame(raf);observer.disconnect();el.removeEventListener("pointermove",move);el.removeEventListener("pointerleave",leave);};
  },[quiet,mini,analyser]);
  return <canvas ref={canvas} className={mini ? "presence-canvas mini" : "presence-canvas"} role="img" aria-label={`Jarvis: ${mode}`}/>;
}
