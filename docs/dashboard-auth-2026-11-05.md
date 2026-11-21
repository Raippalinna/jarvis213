# JARVIS dashboard – Supabase backendautentisering, 2026-11-05

## Problem och avgränsning

Det tidigare driftsatta Edge API:t använder enbart legacy `SUPABASE_SERVICE_ROLE_KEY` som både `apikey` och Bearer-token. En framtida övergång till en `sb_secret_`-nyckel utan ändrad headerhantering ger 401 eftersom nyckeln inte är en JWT. Dessutom godtas dashboardlösenord i URL-parametern `?k=`, vilket kan läcka i URL-historik och serverloggar.

**Nyckelbaserad 401-hypotes är inte bekräftad som grundorsaken till aktuella anrop.** Två anonyma 401 på dashboard-endpointen har setts i Edge-logg; ett förväntat avslag mot obehöriga är inte ett driftfel.

## Ändring

- Föredra backend-only `SUPABASE_SECRET_KEY=sb_secret_...`; legacy `SUPABASE_SERVICE_ROLE_KEY` är fallback.
- Modern hemlig nyckel skickas **endast** som `apikey`; legacy JWT skickas i `apikey` och `Authorization: Bearer`.
- Lås Supabase-URL till rätt projekt före nätverksanrop.
- Acceptera **enbart** `x-jarvis-key` för dashboardauth. Query-parametern `?k=` tas bort som avsiktlig säkerhetsändring.
- Inga ändringar av `DRY_RUN`, `Approval Center`, kill switch, AI-budget, modellrouting, databasschema eller kostnadsdrivande workflows.

## Verifiering

`node --test tests/test_dashboard_auth_contract.mjs` kontrollerar headerlägen, bortvald URL-credential, felaktiga nycklar och fel projektadress i isolerad miljö. GitHub Actions-filen `.github/workflows/jarvis-dashboard-auth-contract.yml` kör samma prov utan GitHub secrets.

Offline-PASS är **inte live-PASS**. Innan driftsättning behövs en separat, ägargodkänd kontroll i Supabase Edge Functions med riktig server-only nyckel, en behörig headerbaserad `health`-request och en obehörig request som ska ge 401. Gamla klienter som använder `?k=` måste migreras till `x-jarvis-key` före release.

## Rollback

Stäng PR utan merge (ingen driftpåverkan). Efter eventuell merge revert:a ändringarna i edge-filen och testerna. Ingen databasåterställning behövs.
