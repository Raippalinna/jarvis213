# JARVIS Ω∞ – verifierat produktionsläge 2026-11-07

**Detta dokument är ett driftbevis, inte ett påstående om att hela JARVIS är färdig.**
Alla kontroller har körts med anslutna GitHub- och Supabaseverktyg.
Inga hemliga nyckelvärden, användartexter eller minnesinnehåll exponeras.

## Produktionsåtgärder genomförda

1. **Minne: ägarbaserad RLS.** Migration
   `jarvis_memory_deny_unscoped_authenticated_reads_20261107` tog bort
   generisk läsning av rader med `user_id IS NULL`.
   Före: syntetisk autentiserad roll såg 77/77 rader. Efter: två skilda
   syntetiska roller såg 0/77. `service_role` läser fortfarande 77/77.
   Inga gamla minnesrader har raderats eller fått gissat ägarskap.
2. **Minnes- och revisionsloggskrivning.** Migration
   `jarvis_memory_audit_write_lockdown_20261107` tog bort öppna
   `anon`-skrivvägar och kräver giltigt `auth.uid()` på vanliga
   minnesändringar.
3. **Konfiguration.** Migration
   `jarvis_system_config_authenticated_read_allowlist_20261107` begränsar
   vanlig läsning till sex tillåtna konfigurationsnycklar. Ett
   syntetiskt autentiserat test såg 0 lösenordshashrader.
4. **Sökfunktionen.** Migration
   `jarvis_memory_search_fixed_search_path_20261107` låser sökvägen.
   Security Advisor-varningen för sökfunktionen försvann.
5. **Chatt och RPC.** Migration
   `jarvis_chat_client_grants_and_anonymous_rpc_lockdown_20261107` tog
   bort `anon` och `authenticated` direktprivilegier på
   `jarvis_chat`; behöll `service_role`. Anonym `EXECUTE` på
   `jarvis_memory_search` stängdes, `authenticated` och
   `service_role` behöll rättigheten. Behörigheterna verifierades
   efteråt. Security Advisor-listan varnade inte längre för
   GraphQL-exponering av `jarvis_chat`.

## API-versioner i produktion

| API | Driftversion | Källa | Verifiering |
|---|---|---|---|
| `jarvis-comet` | 8 | PR #67 | Byte-exakt kodmatchning och anonym HTTP 401 |
| `jarvis-dashboard-api` | 4 | PR #45 | Byte-exakt kodmatchning och internt läs-E2E |
| `jarvis-readonly-preflight-20261107` | 16 | Engångsdiagnostik | Avstängd stub; svarar enbart 401 |

PR #45 åtgärdade dessutom ett **verifierat produktionsfel**:
Supabase serverns moderna `sb_secret_` låg under äldre variabelnamnet
`SUPABASE_SERVICE_ROLE_KEY`, medan `SUPABASE_SECRET_KEY` saknades.
Dashboardens tidigare kodklassificering avvisade detta före nätverksanrop
och gav `chat_list` HTTP 500 och okänd autonomistatus. Uppdaterad kod
klassificerar nyckeln efter `sb_secret_`-format även under äldre
variabelnamnet och skickar den endast som `apikey`, aldrig som Bearer.
Felformat nyckel avvisas fortfarande. Nya syntetiska regressionstester
ingår i PR #45.

**CI-bevis för slutlig PR #45-kod**: GitHub Actions
[run #42327941493](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42327941493)
**4/4 PASS**: JavaScript, Python, dashboard-bygg och samlad kvalitetsgrind.

**Live E2E efter dashboard v4**: Interna, ofarliga API-anrop med
serverlagrad `x-jarvis-key` via Edge, i funktionsloggar:

```text
JARVIS_DASHBOARD_V4_E2E=health_200_autonomy_true_chat_list_200_valid_state_200_valid_llm_absent
```

Det bekräftar att autentisering, konfigurationsläsning, hälsosvar,
chattlistehämtning och dashboardens `state` fungerar i produktion.
Inga privata radvärden loggades eller återlämnades från diagnosfunktionen.
Diagnosen avaktiverades efteråt.

## Återstående blockerare

**P0 – JARVIS GitHub-dispatch är blockerad.**
Isolerat `verify_connection`-anrop med korrekt serverlagrad headernyckel
och aktiv autonomistatus gav **GitHub HTTP 401**, Comet HTTP 502.
Funktionslogg:
`JARVIS_GITHUB_DISPATCH_DIAG=edge_502_github_401`.
Det är den serverlagrade `JARVIS_GITHUB_PAT` som avvisas; inga
vanliga Jarvis-jobb startades. Se
[issue #70](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/70).
GitHub-tokenen måste roteras med avgränsad Contents write-behörighet
för korrekt privat repository, och lagras via Supabase Edge Functions
Secrets **utan att exponeras i chatt eller kod**.

**P0 – GitHub Actions backendnyckel är separat och ej liveverifierad.**
PR #37 har offlinepass men dess skyddade manuella
`workflow_dispatch/live_probe=true` har inte körts. Backendåtkomst i
Supabase Edge bevisar inte att GitHub Actions har rätt secret.

**P1 – Legacy owner/tenant-migrering återstår.**
77 äldre minnesrader saknar `user_id` och är därför server-only.
40 saknar `tenant_id`. De måste klassificeras på verifierad grund innan
individuella användare ska kunna läsa dem.

**Valfritt direkt LLM-läge saknas.** Hälsosvaret rapporterade
`has_llm=false`. Inga LLM-nycklar har skapats och inga modellkostnader
har initierats i verifieringen.

**Klientmigration:** äldre GET med `?k=` fungerar avsiktligt inte
längre mot uppgraderat Comet-API. Klienter behöver
`POST` med JSON och `x-jarvis-key`. Den individuella autentiseringen
för ett framtida multi-tenant-SaaS är fortfarande en separat utveckling.

## Driftgränser och säkerhet

- Inga PR:er har mergats till `main` i enlighet med `AGENTS.md`.
  Versionshistorik och testad källkod finns i PR #37, #45, #67, #68.
- Inga användarkonton har omärkts eller data raderats.
- Ingen global kill switch, DRY_RUN eller Approval Center har öppnats.
- Den tillfälliga Edge-diagnostiken är avslutad och avaktiverad.
- Härdningsmigreringar ska inte återställas för att kringgå behörigheter.

**Status:** Dashboardens läsflöden är driftverifierade och det
verifierade RLS-läsglappet är stängt. GitHub-dispatch och fullständigt
Jarvis Prime E2E är **inte** driftsgodkända innan issue #70 har lösts.


## Fortsatt granskning – 2026-11-07: ytterligare två RLS-luckor

**Verifierat före korrigering:** syntetisk roll `anon` kunde läsa
`public.jarvis_dashboard` (**13 av 13 rader**) och
`public.jarvis_dashboard_v2` (**24 av 24 rader**). Ursprungspolicyerna
`jarvis_dashboard_allow_all` samt `jarvis_dashboard_v2_tenant_isolation`
och `jarvis_dashboard_v2_write_access` tillät bred åtkomst;
`auth.uid() IS NULL` gav anonyma anrop åtkomst.

**Åtgärdat i produktion:** migration
`jarvis_dashboard_anonymous_rls_emergency_lockdown_20261107`
tog bort de tre öppna policyerna och återkallade alla direkta
`anon`/`authenticated`-privilegier på båda interna tabellerna.
Efter verifiering har dessa roller **ingen SELECT/INSERT/UPDATE/DELETE**
på dem. `service_role` behåller samma fyra privilegier. Alla 13+24
rader bevarade. Den interna `jarvis-dashboard-api` använder servernyckel
och inte direktklientens DB-roll.

**Eftertest:** `jarvis-dashboard-api?action=state` med korrekt
intern serverheader svarade HTTP **200**, och svar med giltigt
`generated_at` kom tillbaka (diagnosloggen
`JARVIS_POST_RLS_DASHBOARD=http_200_valid_true_dashboard_list_false`;
`dashboard_list_false` är ett icke-obligatoriskt fält i diagnostikens
typkontroll och **inte** ett HTTP-fel). Inga privata fält loggades.
Diagnosfunktionen `jarvis-readonly-preflight-20261107` återställdes
till **version 18**, som alltid svarar HTTP 401 utan utgående anrop.

Supabases Security Advisors visar efteråt inga
`pg_graphql_anon_table_exposed`-varningar för
`jarvis_dashboard`, `jarvis_dashboard_v2` eller `jarvis_chat`.
`jarvis_license_plans` har kvar sin avsiktliga publika
läsning av aktiva planer. Andra globala varningar i samma Supabase-projekt
är ännu inte åtgärdade eller riskvärderade separat.

**Vercel:** Vercel-anslutningen svarade HTTP 403 med `invalidToken=true`
för listning av projekt. CLI-fallback saknar installerad CLI och
autentisering i arbetsmiljön. Frontendens **produktionsversion**
och eventuellt fortsatt lokal lagring av en gammal dashboardnyckel
kan inte verifieras här. Se
[issue #71](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/71).

**Incidentbedömning:** att RLS tillät anonym läsning tidigare är
en verifierad åtkomstbrist, men utan separat loggbevis ska ingen påstå att
faktiska data har exfiltrerats. Om externa användare har använt de
gamla tabellerna direkt kan det ha uppstått kompatibilitetsbrott;
kontrollera med Vercel/integrationsägare innan nästa klientrelease.
