# Edge Canary Deployment – 2026-11-07

## Produktionsprojekt (separata canaries)

Projekt: `fzmnqvmfilqizzftphbt` (`ACTIVE_HEALTHY`).

| Funktion | Status | Version | Källa / verifiering |
|---|---|---:|---|
| `jarvis-comet-secure` | ACTIVE | 1 | Exakt samma `index.ts` som GitHub-grenen `security/comet-auth-tenant-guard-20261107` (PR #67) |
| `jarvis-dashboard-secure` | ACTIVE | 1 | Exakt samma `index.ts` som GitHub-grenen `security/dashboard-auth-hardening-20261105` (PR #45) |

**Kontroll:** Supabase `get_edge_function` returnerade båda deployade
filernas innehåll, som jämfördes byte för byte med respektive GitHub-version.
Båda har `verify_jwt=false` på plattformsnivå eftersom koden hanterar
`x-jarvis-key` själv. Det är **inte** bevis för ett lyckat autentiserat anrop.

Funktionerna svarar på skilda URL:er:

- `https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet-secure`
- `https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-dashboard-secure`

De äldre `jarvis-comet` och `jarvis-dashboard-api` har **inte** ersatts.
Inga produktionsklienter har migrerats automatiskt.

## Testbevis

- PR #67, commit `e56afcb8d2d153398f7189034232d90009d6c4c8`,
  [Actions #42321387516](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42321387516):
  **4/4 kvalitetsjobb PASS**, inklusive offline-anrop och isolerad check.
- PR #45, commit `61a38a0fa661de8cad5ccea22b73dd4f8c10dc82`,
  [Actions #42118361962](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42118361962):
  **4/4 kvalitetsjobb PASS**, 14/14 JavaScript-tester.

**Live negativt HTTPS-test:** En extern, icke-autentiserad GET-kontroll
2026-11-07 mot `jarvis-comet-secure` och `jarvis-dashboard-secure`
gav **HTTP 401 för båda**. Inga autentiseringsvärden eller privata data skickades.

**Fortfarande ej verifierat:** korrekt header med giltig servernyckel,
autentiserad `202` från Comet, en faktisk GitHub-dispatch, tenantmedlemskap,
korrekt service-role och Notion-kvitto. Att en funktion är ACTIVE och att den
ger 401 för anonyma anrop är inte ett fullständigt end-to-end-driftintyg.

## Överlämningsgrind till befintlig produktionsadress

1. Verifiera att korrekt `JARVIS_ENDPOINT_KEY`, `JARVIS_GITHUB_PAT` och
   rätt Supabase-backendnyckel finns som Edge-secrets.
2. Testa med fiktiv felaktig nyckel → 401 och med korrekt header → förväntat svar.
3. Testa Comet normalroute med pausad autonomi → 423 och blockering av GET,
   URL-credential, tenant-/Notion-override.
4. Migrera alla klienter/bokmärken som använder legacy `?k=`.
5. Genomför godkänd kontrollkörning med kopplat GitHub-run-ID och Notion-kvitto.
6. Först därefter överväg ersättning av `jarvis-comet` och
   `jarvis-dashboard-api`, med dokumenterad rollback.

**Status:** CANARY DRIFTSATT / KOD MATCHAD / OAUTENTISERAD 401 LIVE VERIFIERAD / POSITIV AUTH OCH E2E EJ VERIFIERAD.
