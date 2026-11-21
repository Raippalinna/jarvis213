# Comet: säker klientmigration (förslag, ännu inte driftsatt)

## Nytt anropskontrakt

Endast HTTP POST med `Content-Type: application/json` och `x-jarvis-key`. Delad endpointnyckel får enbart användas av en betrodd serverkomponent eller privat lokal klient, **aldrig av en publik webbsida, bookmarklet eller annan distribuerad klientkod**.
Nyckeln ska injiceras som en skyddad klientkonfiguration (aldrig i URL, HTML, loggar eller GitHub).
Ordinarie uppdrag:

```sh
curl --fail-with-body --request POST "$JARVIS_COMET_URL" \
  --header 'Content-Type: application/json' \
  --header "x-jarvis-key: $JARVIS_ENDPOINT_KEY" \
  --data '{"q":"Testa anslutningen med ett ofarligt uppdrag","tier":"LOW","fmt":"json"}'
```

Isolerat kontrollanrop (måste förbli utan modell-/Notion-uppdrag):

```json
{"action":"verify_connection","check_id":"cc62340c-98bc-409b-9a40-6523e1eade84"}
```

Använd en **ny** UUID v4 för varje körning. Dokumentationens ID är endast ett exempel.
`tenant`, `user_id` och `notion` får inte skickas av klienten.
Denna version använder serverstyrda värden för en enda personlig tenant;
det är **inte** allmän multi-tenant-identitetsverifiering.

## Oberoende produktionsspärr i PR #64

Utöver databasens `system_config.autonomy_enabled` kräver den föreslagna Comet-koden en separat serverinställning `JARVIS_COMET_DISPATCH_ENABLED` med värdet exakt `true`. Saknad eller annan inställning returnerar 423 utan dispatch, även för det isolerade anslutningstestet. Denna spärr är **inte driftsatt** bara för att GitHub Actions passerar.

Innan en framtida driftsättning måste den nya spärren avsiktligt förbli avstängd under uppgradering och negativa tester. Slå inte på den förrän klientinventering, autentisering, nyckelrotation, kostnadsgrind och operativt godkännande är klara. Den aktiva versionens säkerhet kan inte härledas från repots kod.

## Oberoende GitHub Actions-grind (repository_dispatch)

Kod i `.github/workflows/jarvis-cloud.yml` har nu en extra jobbgrind:
`repository_dispatch`-händelser startar inte exekveringsjobbet om inte GitHub-repositoryvariabeln `JARVIS_REPOSITORY_DISPATCH_ENABLED` är exakt `true`. Saknas variabeln är dispatch avstängd. GitHub kan fortfarande ta emot ett event utan att jobbet exekveras: HTTP 204 från GitHub bevisar **inte** att uppdraget har utförts.

Den här grinden skyddar bara `repository_dispatch`. Den påverkar inte manuella `workflow_dispatch` eller anrop från `workflow_call`, som kräver separat behörighetsinventering och säkerhetsgrind. Den börjar inte gälla förrän workflow-filen nått default-branchen, eftersom GitHub hanterar `repository_dispatch` via default-branchen. Sätt **inte** variabeln till `true` före genomförd staging, klientmigration och godkänt produktionsbeslut.

## Säkerhetsbeteende

- 400: ogiltigt schema, URL-parametrar eller klientstyrd destination
- 401: saknad eller felaktig endpointnyckel
- 405: fel metod (t.ex. GET)
- 413/415: för stort anrop respektive fel Content-Type
- 423: databasautonomin är pausad **eller** Comets oberoende servergrind är avstängd (ingen dispatch)
- 503: backendkonfiguration eller autonomistatus kan inte verifieras (ingen avsiktlig dispatch)
- 502: GitHub avvisade dispatch
- 202: JSON-uppdrag accepterat av GitHub (inte bevisat slutfört)

GitHub kan ha accepterat ett uppdrag precis innan timeout; **gör inte blinda omförsök**.
Ingen upstream-feltext, nyckel eller intern serverrespons ska returneras till klienten.

## Kontroll före release

1. Inventera verkligt installerade Comet-, n8n-, mobil- och MCP-klienter, inte enbart exempel i GitHub. Migrera gamla Comet-anrop från `GET ?k=` till POST + header och flytta delad nyckel till en betrodd server eller lokal secrets-konfiguration. Webbläsarklienter ska använda egen kortlivad användarautentisering genom en separat backend.
2. Rotera `JARVIS_ENDPOINT_KEY` om den förekommit i URL:er/loggar.
3. Kör det nyckelfria CI-testet, därefter staging med giltig nyckel och negativtester.
4. Verifiera `SUPABASE_SECRET_KEY` (endast server-side). Fallback till legacy JWT får endast ha `role=service_role`.
5. Verifiera pausad autonomi, fel tenant/destination, fel metod och normal dispatch genom GitHub run-ID.
6. Bekräfta Supabase Edge Function JWT-inställning, CORS-klienter och legitim användarupplevelse.
7. Release kräver separat godkännande, dokumenterad rollback och efterföljande livekontroll. PR #64 (implementation) och stängd test-PR #65 är inte driftbevis.
8. Granska aktiv `autonomy_enabled` och Comet-servergrinden separat. Kontrollera att en avstängd servergrind hindrar både vanlig och isolerad dispatch innan den tillåts aktiveras.
9. PR #65 gav 8/8 gröna offlineflöden på commit `72ab3d1f9505b82c4c15a116b99bd163bf9140a1`, inklusive PostgreSQL 17. Supabase live-preflight hoppades över. Alltså återstår staging och separat produktionstest.

Inga database-migrationer, prod-secrets eller produktionsdeployment omfattas av denna PR.
