# JARVIS – säkerhetsåtgärder och verifiering 2026-11-07

Detta är en driftrapport med utförda åtgärder och kvarstående hinder.
Sekretess: inga API-nycklar, personuppgifter eller minnesinnehåll citeras.

## 1. Verifierad RLS-korrigering

Databas: Supabase `fzmnqvmfilqizzftphbt`. Migration:
`jarvis_memory_deny_unscoped_authenticated_reads_20261107`.

```sql
ALTER POLICY jarvis_memory_owner_select ON public.jarvis_memory
TO authenticated
USING (auth.uid() IS NOT NULL AND user_id = auth.uid());
```

- Före: en syntetisk `authenticated`-roll såg **77 av 77** minnesrader
  eftersom tidigare policy hade `OR user_id IS NULL`.
- Efter: två olika syntetiska `authenticated`-roller med skilda test-ID:n
  såg **0 av 77**. Båda kontrollerna gjordes som `BEGIN READ ONLY`,
  `SET LOCAL ROLE authenticated` och `ROLLBACK`.
- `anon`: saknar SELECT-grant på `jarvis_memory`.
- `service_role`: kan alltjämt läsa **77 av 77** minnesrader.
- 77 rader finns kvar, alla med `user_id IS NULL`; 40 saknar
  `tenant_id`. Data har **inte ommärkts** med gissat ägarskap.
- Obs: gamla oskopade rader är därför numera avsiktligt **endast
  tillgängliga via privilegierad backend**, tills en korrekt ägarmigrering
  är klar.

Äldre migrationer samma dag `jarvis_memory_audit_write_lockdown_20261107`
och `jarvis_system_config_authenticated_read_allowlist_20261107`
förhindrar direkt anonym inmatning i minne/revision och allmän läsning
av `dashboard_password_sha256`. Syntetisk autentiserad roll såg 0
lösenordshashrader och 6 tillåtna konfigurationsrader.

## 2. Sök-RPC säkerhetsvarning åtgärdad

Migration: `jarvis_memory_search_fixed_search_path_20261107`.

```sql
ALTER FUNCTION public.jarvis_memory_search(
    vector,text,integer,real,text[],text[]
) SET search_path = pg_catalog, public;
```

Efteråt: `prosecdef=false` (SECURITY INVOKER), fast
`search_path=pg_catalog, public`, syntetiskt obehörigt RPC-test 0 rader.
Den tidigare `function_search_path_mutable`-varningen finns inte längre
i Supabases Security Advisors.

## 3. Säkerhetsuppgraderade ordinarie API:er

Två tidigare förberedda och CI-testade Edge-versioner är installerade
på de **ordinarie** adresserna:

- `jarvis-comet` version **8** från PR #67.
- `jarvis-dashboard-api` version **3** från PR #45.

Supabase `get_edge_function` jämfördes byte för byte med respektive
GitHub-branch. Båda är `ACTIVE`, `verify_jwt=false` eftersom
funktionerna själva verifierar `x-jarvis-key`. Anonyma externa GET gav
HTTP **401** för båda.

**Viktig breaking change:** äldre anrop med `?k=`, GET-dispatch eller
lösenords-hashfallback utan explicit flagga kan inte längre användas.
Klienter måste använda header `x-jarvis-key` och vid dispatch POST
med JSON. Behåll inte gamla URL-nycklar i bokmärken eller loggar.
Ingen klient har migrerats automatiskt genom denna Edge-deploy.

## 4. Driftprov från Supabase Edge

En temporär `jarvis-readonly-preflight-20261107` användes endast
för begränsade driftkontroller och återställdes slutligen till **version
9** som alltid svarar 401 och inte gör utgående anrop.

- Backend REST-läsning av `autonomy_enabled`, minnes-ID och
  revisionsloggens ID: `JARVIS_BACKEND_READONLY_PREFLIGHT=read_ok`.
- Två säkra canaryfunktioner autentisering:
  `comet_valid_pass|comet_invalid_pass|dashboard_valid_pass|dashboard_invalid_pass`.
  Testerna använder en hemlighet internt utan att returnera eller logga
  dess värde. Den godkända vägen använder ofarliga metoder/okänd action
  som **inte** startar en normal Jarvis-körning.
- Isolerad kontroll `verify_connection` på ordinarie `jarvis-comet`
  nådde GitHub-dispatch men mottog **GitHub HTTP 401**, via Comet HTTP
  502. Intern logg `JARVIS_GITHUB_DISPATCH_DIAG=edge_502_github_401`.
  Korrelation: `ec912b4e-50ae-4ae8-927f-e2ab934e5d43`.
  Ingen normal `jarvis-run` startades och ingen modellkörning begärdes.

## 5. Kvarvarande blockerare och verifieringskrav

**P0 – GitHub PAT**: [Issue #70](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/70).
Serverlagrad `JARVIS_GITHUB_PAT` avvisas av GitHub med HTTP 401.
En ny giltig credential med repository Contents: write måste sättas
i Supabase Edge secrets. Ingen möjlighet i anslutna verktyg att skapa
en ny användar-PAT eller skriva en hemlighet utan värde. Lägg aldrig
tokenen i chatt.

**P0 – GitHub Actions Supabase backendnyckel**:
[Issue #13](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/13)
och PR #37. Det skyddade `workflow_dispatch/live_probe=true` har
inte körts. Godkänd Edge backendanslutning verifierar **inte** GitHub
Actions egen credential.

**P1 – Legacy minnesägarskap**:
[Issue #69](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/69).
Det generella RLS-läsglappet är åtgärdat, men 77 tidigare oskopade
rader behöver mappas mot verifierad ägare/tenant eller hållas
backend-only. Ingen ommärkning får ske på gissning.

**P1 – Kund-/appflöden:** Byt klienternas URL-credentials till
`x-jarvis-key`; inför individuella användarsessioner/tenantregler
före fleranvändarversion; verifiera korrekt 202/204 samt GitHub run-ID,
utan att kringgå autonomigrind eller Approval Center.

## 6. Rollback och efterkontroll

- Alla migrationssteg är registrerade i Supabase, befintliga minnesrader
  bevarade. Återintroducera aldrig öppna RLS-policyer som snabb rollback.
- Tidigare Comet v7 och dashboard v2 ersattes. Kod för föregående
  dashboard finns i `main`; föregående Comet v7 skilde sig från `main`
  endast genom CORS-headern. Återställ helst genom granskad ny deploy
  efter riskbedömning, inte genom att återaktivera `?k=`-auth.
- Kontrollera aktuell version och granskningsresultat efter varje senare
  client- eller secret-rotation.

**Status:** P0 RLS STÄNGD OCH VERIFIERAD; CANONICAL AUTH DRIFTSATT OCH
DELTESTAD; GITHUB DISPATCH BLOCKERAD AV EXPLICIT 401; FULL END-TO-END
EJ GODKÄND.
