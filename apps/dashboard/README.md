# JARVIS Kontrollrum (dashboard)

Mobilanpassad PWA för Jarvis: KPI, initiativ, systemläge, connector-hälsa, händelser, minne och chatt med JARVIS Prime.

- Frontend: Vite + React + Tailwind; statisk export (`npm run build` → `dist/`).
- Backend: Supabase Edge Function `supabase/functions/jarvis-dashboard-api`; modern `SUPABASE_SECRET_KEY` används server-side som `apikey`, legacy `SUPABASE_SERVICE_ROLE_KEY` som JWT-fallback. Fel projekt-origin och HTTP-redirects avvisas.
- Chatt: `prime` = `repository_dispatch` med `JARVIS_GITHUB_PAT`; `instant` = LLM om `LLM_API_KEY` finns på servern.
- Inloggning: `x-jarvis-key`-header med `JARVIS_ENDPOINT_KEY` (lång slumpmässig nyckel i Supabase Secrets). **Inga URL-nycklar.**
- Lagring: nyckeln ligger i minnet och `sessionStorage` (per flik). Gammal `localStorage`-post rensas; användaren kan behöva logga in igen.
- Legacy lösenord (`system_config.dashboard_password_sha256`) godkänns enbart om servern **uttryckligen** har `JARVIS_ALLOW_LEGACY_PASSWORD=true`. Behåll den som tillfällig övergång; använd `JARVIS_ENDPOINT_KEY` i normal drift.
- Serverns `system_config`-svar begränsas till `autonomy_enabled`; andra interna värden får inte skickas till dashboarden.

Detta är **delad nyckelautentisering**, inte personliga konton eller tenant-säker RBAC. För fleranvändar-/SaaS-drift krävs Supabase Auth och RLS per användare/tenant.

Bygg lokalt: `npm ci && npm run build` i `apps/dashboard`. `VITE_JARVIS_API_URL` kan peka mot önskad Edge-miljö; använd aldrig en `VITE_*`-variabel för hemligheter.

Kontroll: `node --test tests/test_dashboard_auth.mjs` från repositoryroten. Se [autentiseringsdokumentationen](../../docs/authentication.md) för requestflöden, rest-risker och produktionsgrindar.
