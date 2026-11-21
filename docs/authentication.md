# Autentisering och tokenflöden — JARVIS Ω∞ OS v2

**Kodgranskning 2026-11-05.** Detta dokument beskriver repositorykoden, inte en verifiering av driftsatt Supabase, GitHub Actions eller användarnas aktiva sessioner. Inga hemliga värden ska dokumenteras.

## Komponenter och behörighetsgränser

| Komponent | Kod | Identitet / credential | Åtkomst |
|---|---|---|---|
| Dashboard PWA | `apps/dashboard/src/api.ts` | Delad nyckel i `x-jarvis-key`, endast minne/sessionStorage | Begäran till Edge Function; inte en personlig session |
| Dashboard Edge Function | `supabase/functions/jarvis-dashboard-api/index.ts` | `JARVIS_ENDPOINT_KEY` + `SUPABASE_SECRET_KEY` (eller legacy service-role) i Supabase Secrets | Backendläsning, chattskrivning, GitHub-dispatch |
| Comet Edge Function | `supabase/functions/jarvis-comet/index.ts` | Legacy header eller URL `?k=` | Separat endpoint. URL-hemligheter är en kvarstående risk |
| GitHub Actions / JARVIS | `.github/workflows/jarvis-cloud.yml`, `jarvis_cloud.py` | Repository/PAT-kontroll före dispatch; GitHub Actions Secrets till jobb | Utför task med budget- och godkännandegrindar |
| Supabase personlig minnessession | `src/jarvis/memory/session.py` | `Authorization: Bearer <access_token>` + `apikey: sb_publishable_...` | `/auth/v1/user` verifierar identitet; RLS måste separat upprätthålla medlemskap |
| Backendminne och godkännandelogg | `src/jarvis/memory/`, `src/jarvis/approval/gate.py` | Serverhemlighet för Supabase | Privilegierade databasoperationer; **inte** användar-JWT |

## Requestflöde: dashboard

1. Användaren matar in Jarvis-nyckeln. Den lagras endast i minnet och `sessionStorage`; äldre `localStorage`-post rensas utan att återanvändas.
2. Klienten gör `POST /functions/v1/jarvis-dashboard-api` med JSON-body `{ "action": "state" }` och header `x-jarvis-key`.
3. Servern avvisar `?k=` i URL (även tillsammans med en giltig header), saknad/ogiltig nyckel samt nycklar med yttre blanksteg.
4. Servern jämför hashade värden utan tidig exit. `JARVIS_ENDPOINT_KEY` är enda standardmetoden. Legacy `system_config.dashboard_password_sha256` kräver **explicit** `JARVIS_ALLOW_LEGACY_PASSWORD=true`, endast för kort migration.
5. Efter autentisering kan `state` läsa godkända dashboarddata; `system_config` begränsas redan vid DB-frågan till `autonomy_enabled`. `chat_send` kan ge instant-svar eller, om kill switch tillåter, server-till-server-dispatch med `JARVIS_GITHUB_PAT`.
6. Supabase REST-anrop låses till förväntad projekt-origin. En modern `sb_secret_` skickas enbart som `apikey`, medan legacy service-role JWT använder `apikey` + `Authorization: Bearer`. Redirects avvisas för databas-, LLM- och GitHub-dispatchanrop.
7. Webbläsaren får aldrig `SUPABASE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `JARVIS_GITHUB_PAT` eller LLM-nyckeln i API-svaret.

**Viktigt:** Det är fortfarande en delad åtkomstnyckel. Den visar inte *vilken användare* som anropar. För produktion med flera användare/tenants ska Supabase Auth med individuella JWT:er, rollkontroll och RLS användas. En delad servernyckel ersätter inte RBAC.

## Requestflöde: personlig minnessession

1. En betrodd server får ett Supabase access-token och ett efterfrågat tenant-id.
2. `verify_session` kontrollerar tokenformat, korrekt publishable-key-format och UUID.
3. `GET https://fzmnqvmfilqizzftphbt.supabase.co/auth/v1/user` med `Authorization: Bearer <user JWT>` och `apikey: sb_publishable_...` måste returnera en autentiserad användare.
4. Användar-id och tenant-id binds till en kortlivad `ContextVar` via `bind_session`. Tenant-id från klienten är **aldrig** medlemskapsbevis; databasens RLS och tenant-medlemskontroll är separata krav.
5. Fält som innehåller tokens har `repr=False`, men detta skyddar inte i sig mot alla former av serialisering och loggning. Logga aldrig sessionsobjekt som JSON.

## Hemligheter och hantering

| Namn | Typ | Ska lagras | Får aldrig placeras |
|---|---|---|---|
| `JARVIS_ENDPOINT_KEY` | Lång slumpmässig delad nyckel | Supabase Edge Secrets; tillfälligt på klienten efter manuell inmatning | Query-string, loggar, repository, `VITE_*` |
| `JARVIS_GITHUB_PAT` | Fine-grained GitHub token | Endast Supabase Edge Secrets | Browser, HTML, URL, API-svar |
| `SUPABASE_SECRET_KEY` | Modern server-nyckel | GitHub Actions Secrets / betrodd server | Klientkod, `VITE_*`, loggar |
| `SUPABASE_SERVICE_ROLE_KEY` | Legacy service-role JWT | GitHub Actions Secrets / betrodd server | Klientkod, `VITE_*`, loggar |
| `sb_publishable_...` | Publik Supabase-nyckel | Klient/betrodd server efter behov | Får **inte** användas som privilegierad backendnyckel |
| `NOTION_TOKEN`, `SLACK_WEBHOOK_URL`, `LLM_API_KEY` | Tjänstehemligheter | Respektive serverhemlighetslager | Klient, repository och loggar |

För den öppna Supabase-fixen gäller: [issue #13](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/13) och [draft PR #37](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/37). PR #37 skiljer moderna secret keys från legacy JWT-bearer och innehåller en skrivskyddad preflight. Den är inte mergad och ett grönt enhetstest är inte ett godkänt driftprov.

## Kvarstående risker och migrering

1. **P0 – Supabase backend 401:** kontrollera att rätt nyckeltyp är installerad i rätt secrets, kör PR #37:s read-only preflight, följt av separat godkänt skriv-/återläsningsprov och tenanttest. Rotera eventuell felhanterad nyckel. Ändra inte kill switch för att kringgå fel.
2. **P1 – Comet legacy GET med `?k=`:** refaktorera i en *separat* kompatibilitetsgranskad PR. Query-hemligheter kan hamna i historik och loggar. Rensa exponerade URL:er och rotera de berörda nycklarna.
3. **P1 – personlig behörighet:** migrera dashboard till Supabase Auth med individuella JWT, tenant-medlemskap och RLS. En delad nyckel ska inte användas för en framtida multi-tenant SaaS.
4. **P1 – äldre lösenord:** om lösenords-SHA256 används: konfigurera först en lång slumpmässig `JARVIS_ENDPOINT_KEY` och testa inloggning; ta därefter bort legacy SHA256-konfigurationen. `JARVIS_ALLOW_LEGACY_PASSWORD` ska normalt saknas eller vara `false`.
5. **P2 – skydd mot bruteforce:** bygg rate limiting per identitet/IP samt övervakning innan en publik fleranvändarlösning tas i drift. Endpointnyckelns styrka ersätter inte begränsning av försök.
6. **P2 – CORS:** nuvarande wildcard tillåter anrop från andra webboriginer när de *redan* har nyckeln. Lås till verifierad produktionsorigin vid driftsättning och kontrollera mobil/PWA.
7. **P2 – sessionStorage:** begränsar persistens jämfört med localStorage men skyddar **inte** mot aktiv XSS eller komprometterad webbläsare.

## Offline-verifiering och driftsättning

Kör på säker lokal kopia av grenen:

```sh
node --test tests/test_dashboard_auth.mjs
cd apps/dashboard && npm ci && npm run build
```

Testet använder syntetiska nycklar, ingen nätverkstrafik och ingen GitHub-dispatch. Det validerar bara den isolerade autentiseringsdelen, config-allowlist och klientens lagring.

**Releasegrind:** säkerhetsgranska diffen, bygg klienten, verifiera med stagingnycklar, testa avvisad/felaktig/giltig inloggning, testa `state` och `chat_send` med autonomi pausad, verifiera att inga hemligheter finns i URL/loggar/respons, rotera exponerade nycklar och inhämta godkännande innan merge/deploy. Ingen produktionsändring ingår i denna PR.

**Återställning:** stäng PR:n utan merge, eller revert berörda commits efter godkänd release om ett kompatibilitetsfel upptäcks.
