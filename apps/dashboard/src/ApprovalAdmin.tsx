import { useCallback, useState } from "react";

// Independent Supabase Auth identity for privileged approvals.
// The normal shared Jarvis dashboard key is NOT accepted for decisions.
// An operator must separately enroll the verified auth user in
// public.jarvis_approval_admin after proving ownership.
const PROJECT = "https://fzmnqvmfilqizzftphbt.supabase.co";
const APPROVAL_URL = PROJECT + "/functions/v1/jarvis-approval-admin";
const PUBLIC_KEY = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined) ??
  (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? "";

type Pending = {
  request_id: string;
  title: string;
  risk_class: "R2" | "R3";
  expires_at: string;
  action_bound: boolean;
};

export default function ApprovalAdmin() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [jwt, setJwt] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const [status, setStatus] = useState("Verifierad personlig inloggning krävs för godkännanden.");
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const configured = PUBLIC_KEY.startsWith("sb_publishable_") ||
    (PUBLIC_KEY.split(".").length === 3 && !PUBLIC_KEY.startsWith("sb_secret_"));

  const authCall = async (path: string, body: Record<string, unknown>) => {
    const res = await fetch(PROJECT + "/auth/v1/" + path, {
      method: "POST",
      redirect: "error",
      headers: { apikey: PUBLIC_KEY, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res;
  };

  const requestOtp = async () => {
    if (!configured || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || busy) return;
    setBusy(true);
    try {
      const r = await authCall("otp", { email: email.trim(), create_user: true });
      setStatus(r.ok
        ? "Kontrollera e-post. Ange engångskoden. Om bara en inloggningslänk skickas behöver OTP-mallen aktiveras i Supabase Auth."
        : "E-postinloggning misslyckades. Kontrollera e-postleverans och Auth-inställningar.");
    } catch {
      setStatus("Det gick inte att ansluta till Supabase Auth.");
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async () => {
    if (!configured || otp.trim().length < 4 || busy) return;
    setBusy(true);
    try {
      const r = await authCall("verify", {
        email: email.trim(), token: otp.trim(), type: "email",
      });
      const data = await r.json().catch(() => ({})) as { access_token?: string };
      if (!r.ok || !data.access_token) {
        setStatus("Koden kunde inte verifieras.");
        return;
      }
      // In-memory only: never store Auth JWT in localStorage or the URL.
      setJwt(data.access_token);
      setOtp("");
      setStatus("Inloggad. Hämtar endast dina behöriga godkännanden.");
      await fetchPending(data.access_token);
    } catch {
      setStatus("Identitetsverifieringen misslyckades.");
    } finally {
      setBusy(false);
    }
  };

  const fetchPending = useCallback(async (token: string) => {
    try {
      const r = await fetch(APPROVAL_URL, {
        method: "POST", redirect: "error",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify({ action: "list" }),
      });
      if (r.status === 401) {
        setJwt("");
        setPending([]);
        setStatus("Sessionen har löpt ut. Logga in igen.");
        return;
      }
      if (r.status === 403) {
        setPending([]);
        setStatus("Identiteten är verifierad men inte registrerad som Jarvis-administratör. En projektägare måste göra en separat, granskad behörighetskoppling.");
        return;
      }
      if (!r.ok) {
        setStatus("Approval-tjänsten är inte klar för drift. Ingen åtgärd utfördes.");
        return;
      }
      const data = await r.json() as { pending?: Pending[] };
      setPending(Array.isArray(data.pending) ? data.pending : []);
      setStatus("Godkännanden hämtade. Endast giltiga, uppdragsbundna beslut kan godkännas.");
    } catch {
      setStatus("Godkännandetjänsten är otillgänglig. Ingen åtgärd utfördes.");
    }
  }, []);

  const decide = async (item: Pending, response: "approved" | "rejected") => {
    if (!jwt || !item.action_bound || busy) return;
    if (!window.confirm(
      response === "approved"
        ? "Bekräfta godkännande av " + item.risk_class + ":\n" + item.title + "\n\nDetta ger inte rätt att kringgå release- eller kostnadsspärrar."
        : "Avslå detta beslut?\n" + item.title,
    )) return;
    setBusy(true);
    try {
      const r = await fetch(APPROVAL_URL, {
        method: "POST", redirect: "error",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + jwt },
        body: JSON.stringify({
          action: "decide", request_id: item.request_id,
          decision: response, reason: reason.slice(0, 500) || undefined,
        }),
      });
      setStatus(r.ok ? "Beslutet registrerades. Ingen agent har verkställts automatiskt."
        : "Beslutet kunde inte registreras. Det kan vara utgånget eller redan hanterat.");
      if (r.ok) await fetchPending(jwt);
    } catch {
      setStatus("Backendavbrott: inget beslut bekräftat.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="grid gap-4 max-w-3xl mx-auto">
      <div className="panel p-5">
        <h2 className="text-xl font-semibold mb-2">Approval Center – säker administration</h2>
        <p className="text-sm text-muted mb-4">{status}</p>
        {!configured && <p className="text-sm text-rose">Saknar publik Supabase-konfiguration: VITE_SUPABASE_PUBLISHABLE_KEY. Lägg aldrig in servernycklar här.</p>}
        {!jwt ? (
          <div className="grid gap-3 max-w-md">
            <label className="text-sm">E-postadress för Supabase Auth
              <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email"
                type="email" className="w-full mt-1 p-2 rounded-md border border-line bg-bg" placeholder="din e-postadress" />
            </label>
            <button disabled={!configured || busy} onClick={requestOtp}
              className="py-2 px-3 rounded-md border border-line disabled:opacity-40">Skicka engångskod</button>
            <label className="text-sm">Engångskod från e-post
              <input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric"
                className="w-full mt-1 p-2 rounded-md border border-line bg-bg" placeholder="Kod" />
            </label>
            <button disabled={!configured || busy} onClick={verifyOtp}
              className="py-2 px-3 rounded-md border border-line disabled:opacity-40">Verifiera identitet</button>
          </div>
        ) : (
          <div className="flex gap-2">
            <button disabled={busy} onClick={() => fetchPending(jwt)} className="p-2 border rounded-md border-line">Uppdatera</button>
            <button onClick={() => { setJwt(""); setPending([]); setStatus("Utloggad."); }} className="p-2 border rounded-md border-line">Logga ut</button>
          </div>
        )}
      </div>
      {jwt && pending.length > 0 && <div className="panel p-5 grid gap-4">
        <label className="text-sm">Motivering (valfri, max 500 tecken)
          <input maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)}
            className="w-full mt-1 p-2 rounded-md border border-line bg-bg" />
        </label>
        {pending.map((item) => <div key={item.request_id} className="border border-line rounded-md p-3">
          <strong>{item.title}</strong>
          <p className="text-xs text-muted">{item.risk_class} · Sista giltighet {item.expires_at}</p>
          {!item.action_bound ? <p className="text-xs text-rose mt-2">Äldre begäran saknar verifierbar uppdragsbindning. Godkännande spärrat.</p> :
            <div className="flex gap-2 mt-3">
              <button disabled={busy} onClick={() => decide(item, "approved")} className="p-2 rounded-md border border-line disabled:opacity-40">Godkänn</button>
              <button disabled={busy} onClick={() => decide(item, "rejected")} className="p-2 rounded-md border border-line disabled:opacity-40">Avslå</button>
            </div>}
        </div>)}
      </div>}
    </section>
  );
}
