/**
 * Strict navigation-only validation for a Perplexity Computer task, artifact, or session.
 * It is NOT a credential check, API connection, or proof of access.
 * Do not persist, log, or send the entered private URL to our backend.
 */
export type PerplexityLinkCheck =
  | { ok: true; href: string }
  | { ok: false; reason: string };

const PERPLEXITY_PATH = /^\/(?:computer\/(?:a|tasks)|session)\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TRUSTED_HOSTS = new Set(["perplexity.ai", "www.perplexity.ai"]);

export function validatePerplexityComputerLink(input: string): PerplexityLinkCheck {
  const value = input.trim();
  if (!value) return { ok: false, reason: "Klistra in länken till din privata Computer-uppgift eller session." };
  if (value.length > 1024 || /[\\\u0000-\u001f\u007f]/.test(value)) {
    return { ok: false, reason: "Länken innehåller ogiltiga tecken eller är för lång." };
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return { ok: false, reason: "Ange en fullständig HTTPS-länk till Perplexity." };
  }
  if (parsed.protocol !== "https:" || !TRUSTED_HOSTS.has(parsed.hostname.toLowerCase()) ||
      parsed.username || parsed.password || parsed.port || parsed.search || parsed.hash ||
      !PERPLEXITY_PATH.test(parsed.pathname)) {
    return { ok: false, reason: "Endast Computer-uppgifter, artefakter eller sessioner från perplexity.ai tillåts." };
  }
  return { ok: true, href: `https://www.perplexity.ai${parsed.pathname}` };
}
