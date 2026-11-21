import { useState } from "react";
import { Badge, Panel } from "./components";
import { validatePerplexityComputerLink } from "./perplexity-url";

/** Manual handoff: no proxy, authentication impersonation, URL storage or API billing. */
export function PerplexityComputerHandoff() {
  const [url, setUrl] = useState("");
  const checked = validatePerplexityComputerLink(url);

  return (
    <Panel title="Perplexity – privat kontrollrum" right={<Badge tone="amber">Ej API-ansluten</Badge>}>
      <p className="text-sm text-muted">
        Öppna en privat Computer-uppgift eller session i Perplexity med din befintliga inloggning.
        Den här bryggan överför ingen data, gör inga API-anrop och ger inte tillgång
        till uppgiften utan korrekt behörighet.
      </p>
      <label htmlFor="perplexity-computer-url" className="block text-xs text-muted mt-4 mb-1">
        Länk till Computer-uppgift eller session
      </label>
      <input
        id="perplexity-computer-url"
        type="url"
        autoComplete="off"
        spellCheck={false}
        maxLength={1024}
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        placeholder="https://www.perplexity.ai/computer/tasks/…"
        className="w-full rounded-md border border-line bg-black/30 px-3 py-2 text-sm outline-none focus:border-cyan/60"
      />
      {url.trim() && !checked.ok && <p role="alert" className="text-xs text-amber mt-2">{checked.reason}</p>}
      <div className="mt-3 flex items-center gap-3">
        {checked.ok ? (
          <a className="inline-flex rounded-md border border-cyan/50 px-3 py-2 text-sm text-cyan hover:bg-cyan/10"
            href={checked.href} target="_blank" rel="noopener noreferrer">
            Öppna i Perplexity
          </a>
        ) : (
          <span className="inline-flex rounded-md border border-line px-3 py-2 text-sm text-muted" aria-disabled="true">
            Öppna i Perplexity
          </span>
        )}
        {url && <button type="button" className="text-xs text-muted underline" onClick={() => setUrl("")}>Rensa länken</button>}
      </div>
      <p className="text-xs text-muted mt-3">
        Integrationsstatus är ej verifierad. Klistra inte in lösenord eller tokens.
        Länken lagras inte och skickas inte till Jarvis-servern.
      </p>
    </Panel>
  );
}
