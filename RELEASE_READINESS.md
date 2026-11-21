# JARVIS Ω∞ — samlad releasekandidat och verifieringsgrindar

Datum: 2026-11-05. Kanoniskt repo: `rickyraippalinna/jarvis-omega-v2`. Huvud-PR: [#53](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/53).

**Status: kod samlad i separat branch. Offline-CI och relevanta stagingprov krävs på exakt senaste head. Ingen merge, SQL-migration eller produktionsdriftsättning ingår.**

## Ändringspaket som sammanförts

| Ursprung | Funktion | Status/begränsning |
|---|---|---|
| [#37](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/37) | Backendnycklar, säker preflight, minne/audit | Nyckelfria tester ≠ autentiserad liveverifiering |
| [#45](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/45) | Dashboard- och Edge-API-auth, header-only | Kräver korrekt klientmigrering |
| [#47](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/47) | Comet POST JSON, auth-header, tenant-/autonomigrind | Legacy GET/?k= slutar fungera; uppdatera klienter först |
| [#48](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/48) | Runtime-policy för modellfallback, maskerade API-fel | Lokala quality-index är inte faktisk modellkvalitet |
| [#49](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/49) | 10 rollspecifika agentkontrakt, DAG, budgetreservation, bevisverifierare | `execution_enabled=False` som standard; inga anslutna live-agentadapters |
| [#54](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/54) | Fail-closed Approval Center, auditkvitto, granskad RLS-lockdown-skiss | SQL ligger i `docs/security/` och är **REVIEW ONLY**, inte tillämpad |

Överlappande äldre PR #25/#42/#44 ersätts **inte** automatiskt; diff och kompatibilitet är dokumenterat granskade på de utvalda versionerna. Separata käll-PR:er ska inte blindmergas ovanpå den samlade kandidaten.

## Skrivskyddad produktionsobservation

Projekt: `fzmnqvmfilqizzftphbt`, Supabase `ACTIVE_HEALTHY` vid kontroll. Edge Functions `jarvis-comet` och `jarvis-dashboard-api` är aktiva, men distribuerade äldre versioner **accepterar query-credentials**. Ingen säkerhetsrättning i denna kandidat är ännu distribuerad. `system_config.autonomy_enabled` observerades som `true`; detta är en konfigurationspost, inte bevis på en lyckad Jarvis-exekvering.

RLS/security-advisors visar exponeringsrisker i Approval Center:
- `approval_decision`: anon SELECT/INSERT/UPDATE och legacy-tenant-policy utan verifierad användaridentitet.
- `approval_request`/`approval_audit_log`: anon INSERT kan vara tillåten.
- Vissa dashboardpolicyer tillåter `auth.uid() IS NULL`; generell grants-inventering behövs.
- Många tabeller är synliga i GraphQL-schemat för `anon` även när RLS blockerar radåtkomst. Schemaexponering **är inte bevis för läckta rader**.
- Följ [P0 issue #52](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/52). **Kör inte** `approval-center-rls-lockdown.review.sql` i produktion utan ett separat releasebeslut.

## Driftgrind (måste utföras i denna ordning)

1. Frys kandidat-SHA; kör `python -m pytest tests -q`, `node --test tests/*.mjs`, `cd apps/dashboard && npm ci --ignore-scripts && npm run build`, och samlat GitHub Actions quality-gate. Grön på **samma SHA**.
2. Inventera alla Perplexity-/Comet-klienter som skickar GET eller URL-parametern `?k=`; ändra dem till `POST`, `Content-Type: application/json`, header `x-jarvis-key` och body med tillåten `q`/`tier`. Nycklar ska aldrig ligga i URI, prompts eller användarsynliga loggar.
3. Migrera dashboardinloggning till header-only. Klientens äldre `localStorage`-inloggning ersätts; ingen nyckel får följa i URL.
4. Kontrollera servernyckel i hemlighetslager **utan att exponera nyckelvärdet**. Modern `sb_secret_...` hör till `apikey`; legacy JWT `service_role` har annan headerhantering.
5. Kör auktoriserad **read-only live/staging-preflight** för `system_config`, `jarvis_memory`, `approval_audit_log`. Stoppa vid okänd roll/host/401.
6. Testa negativt i staging: `autonomy_enabled=false`, fel nyckel, falsk tenant, otillåten Notion-destination, GET/task, payloadgräns, timeout, redirect, R2/R3 utan approval, annan tenants minne. Testa positivt med godkänd identitet och rollbackbar testdata.
7. Kör en icke-kostnadsbärande uppgift från vald klient genom ingress → dispatch → kör-ID → audit → minne → återläsning → Notion, och säkerställ kvitto med **samma run-ID**.
8. Inventera legitima anon-klienter för approval_* och flytta dem till auktoriserad backend. Granska RLS-SQL som *separat* release: migreringsfil från CLI, staging, negativa/positiva behörighetstest och explicit godkännande. Rotera eventuellt exponerad URL-nyckel under kontrollerat fönster.
9. Först därefter: separat godkänd merge, Supabase/Vercel-distribution och verifiering i verklig drift med rollbackplan.

## Driftstatusens sanningsgräns

`CI-verified` ≠ `staging-verified` ≠ `deployed` ≠ `production-verified`. En agentroll och ett lokalt simulerat kvitto bevisar inte att en extern åtgärd utförts. Stäng eller aktivera aldrig kill switch för att passera test. Inga hemligheter, persondata eller live-skrivningar i tester.

## Återställning

Stäng PR #53 utan merge → befintlig `main` och produktion oförändrade. Vid senare godkänd driftsättning: bevara föregående Edge Function-versioner, frontendbuild och migreringsbackup. Ingen automatisk återställning som återinför breda anon-grants.
