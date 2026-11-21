# Jarvis Omega – återställning av Supabase-åtkomst

Den här draft-PR:en korrigerar autentiseringskoden och lägger till verifieringsgrindar. Den ändrar inga produktionshemligheter, kör inga skrivningar och driftsätter ingenting.

## Grundorsak

Den tidigare klienten skickade samma värde i både `apikey` och `Authorization: Bearer`. Det är korrekt för en äldre `service_role`-JWT men fel för Supabases moderna hemliga servernyckel. En publik/anon-nyckel hade dessutom kunnat nå nätverket innan felet upptäcktes.

## Nytt beteende

- `SUPABASE_SECRET_KEY` prioriteras. Den skickas endast i `apikey`.
- `SUPABASE_SERVICE_ROLE_KEY` är en tillfällig legacy-fallback och använder Bearer endast när JWT-rollen är `service_role`.
- Publicerbara, anon, authenticated och okända nyckeltyper stoppas före nätverksanrop.
- Det skrivskyddade förtestet tillåter endast projektet `fzmnqvmfilqizzftphbt.supabase.co`.
- Förtestet läser `system_config`, `jarvis_memory` och `approval_audit_log`; exitkod 0 kräver att autonomi är aktiverad och alla tre läsningar lyckas.
- Felrapporter innehåller statuskoder, aldrig nyckel- eller svarsinnehåll.

## Kräver behörig ägare

1. Skapa eller hämta en giltig hemlig servernyckel i rätt Supabase-projekt. Klistra aldrig in den i en chatt, frontend eller kod.
2. Lägg den i GitHub Actions-secret `SUPABASE_SECRET_KEY`. Behåll legacy-secret bara tills migreringen är verifierad.
3. Kör workflow **Supabase backend diagnostics** manuellt med `live_probe=true`.
4. Godkänn inte merge förrän unit-jobbet och live-förtestet är gröna.
5. Verifiera tenantisolering separat. En backendnyckel kringgår RLS och ett lyckat förtest bevisar inte tenantgränser eller skrivbehörighet.

## Testgrindar

- Fokuserade nyckelfria regressionstester körs automatiskt i PR.
- Full svit: `python -m pytest tests -q`.
- Dashboard: `cd apps/dashboard && npm ci && npm run build && npm audit --omit=dev`.
- PR #5 och #23 integreras först efter konfliktgranskning och verifierad tenantisolering.

## Stoppvillkor

Sammanfoga eller driftsätt inte vid röd CI, misslyckat live-förtest, okänd nyckeltyp eller overifierad tenantisolering.
