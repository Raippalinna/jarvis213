# Autentisering och tokenflöde – JARVIS Ω∞ OS v2

Dokumenterat mot kod på `main` och förslag i `security/dashboard-auth-header-only-20261105` (2026-11-05).
**Ingen driftsättning eller verifiering av live-hemligheter ingår.**

## Komponenter och requestflöde

1. **Dashboard (Vite/React)** – `apps/dashboard/src/api.ts` skickar POST till
   `/functions/v1/jarvis-dashboard-api`. Åtkomstnyckeln ligger i
   `x-jarvis-key`, inte i URL eller request-body. Efter säkerhetsuppdateringen
   sparas den endast i processminne / flikens `sessionStorage`, och gamla
   `localStorage`-kopior rensas utan att läsas. Återinloggning kan krävas.
2. **Edge Function** – `supabase/functions/jarvis-dashboard-api/index.ts`
   nekar saknade/ogiltiga nycklar med HTTP 401. `?k=` avvisas även om
   en giltig header skickas. Serverhemligheten `JARVIS_ENDPOINT_KEY` används
   för jämförelse mot en SHA-256-digest. Den befintliga, äldre fallbacken mot
   `system_config.dashboard_password_sha256` lämnas kompatibel i denna PR,
   men bör avvecklas för mänskliga lösenord.
3. **Databas** – samma funktion skickar backendnyckel enbart från Supabase
   runtime-environment till egna REST-anrop. Privilegierad nyckel får aldrig
   läggas i `VITE_*` eller returneras till klienten.
4. **AI eller GitHub Actions** – `chat_send` kan svara genom serverhemligheten
   `LLM_API_KEY` eller skicka `repository_dispatch` med
   `JARVIS_GITHUB_PAT`. `autonomy_enabled` kontrolleras före
   *Prime-dispatch*. Det är inte ett bevis på individuell användaridentitet.
5. **GitHub workflow** – `.github/workflows/jarvis-cloud.yml` tar emot
   workflow/dispatch-indata via `scripts/resolve_jarvis_inputs.py`; claims i
   `client_payload` är inte autentiserade identitetsbevis. Keys tas från
   GitHub Actions Secrets.
6. **Supabase Auth-session för minnet** – `src/jarvis/memory/session.py`
   använder `apikey: sb_publishable_*` och
   `Authorization: Bearer <användarens access_token>` till
   `GET /auth/v1/user`, utan redirect, och lagrar verifierad användaridentitet
   i en tillfällig ContextVar. Tenantsträngen i anropet är **inte** bevis på
   medlemskap: RLS/membership måste kontrolleras separat.
7. **Approval Gate** – `src/jarvis/approval/gate.py` gör privilegierade
   serveranrop. Dessa ska ha rätt backendroll samt aldrig hoppa förbi
   `DRY_RUN`, kill switch eller godkännandekontroller.

## Hantering av hemligheter

- **Publicerbar Supabase-nyckel** identifierar projektet, inte användaren.
  Den kan förekomma i klienten, men ger inte automatiskt databehörighet.
- **Användarens access token** verifieras av Supabase Auth och skickas bara
  via Authorization-header över HTTPS. Logga inte token.
- **Backendnycklar / service_role / sb_secret** är privilegierade och ska
  bara användas server-side. De måste tillhöra rätt projekt och rätt roll.
  Förväxla aldrig `anon`/publishable med backendbehörighet.
- **GitHub PAT** ska vara fine-grained, endast nödvändiga repos och scopes;
  ska roteras och hållas i Edge Secrets / Actions Secrets.
- **JARVIS_ENDPOINT_KEY** är fortfarande en delad API-nyckel, inte OAuth.
  Lagra inte i URL, loggar eller långlivad webbläsarlagring.
- **SHA-256-lösenord i system_config** är legacy. Migrera till
  Supabase Auth (OAuth/PKCE + serververifiering) alternativt en lämplig
  lösenordshash (Argon2id) med rate limits och unika konton.
- Separata `JARVIS_GITHUB_PAT`, `COMET_API_KEY`, `NOTION_TOKEN` och
  `LLM_API_KEY` får aldrig blandas eller exponeras till frontend.

## Verifierade begränsningar och uppföljning

- Issue [#13](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/13)
  visar tidigare fel backendroll och 401. Draft PR
  [#37](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/37)
  innehåller särskild backend-fix; kräver skyddat live-preflight och
  senare godkända skriv-/RLS-tester innan merge.
- `jarvis-comet` använder fortfarande querynyckeln `?k=` och tillåter
  caller-supplied tenant/user/notion. Migrera klienter till headerbaserad
  POST och gör identitet/destination serverstyrd i separat granskad PR.
  Ändra inte den isolerade connection-check-koden utan att revidera dess tester.
- Dashboard CORS `Access-Control-Allow-Origin: *` är inte en åtkomstkontroll.
  Innan större lansering: explicit allowlist för godkända ursprung.
- Testerna här gäller dashboardens auth-kod isolerat, inte production Edge,
  autentiserade RLS-operationer, GitHub dispatch eller full integration.
- Radera eller rotera hemligheter som redan läckt via URL; ny kod kan inte
  avlägsna äldre proxy-/webbhistorik.

## Nyckelfri verifiering

```sh
node --test tests/test_dashboard_auth.mjs
python -m pytest tests -q
```

Det första kommandot har inga externa API-anrop eller hemligheter.
`pytest` kan kräva lokala beroenden. Kör aldrig tester mot produktion med
riktiga nycklar utan separat godkännande.

**Återställning:** före merge, stäng PR:n. Efter merge, revert av auth-/klient-
commits återställer tidigare beteende men återintroducerar URL-nyckelrisken.
