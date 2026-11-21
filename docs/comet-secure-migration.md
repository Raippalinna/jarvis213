# Comet: säker klientmigration (förslag, ännu inte driftsatt)

## Nytt anropskontrakt

Endast HTTP POST med `Content-Type: application/json` och `x-jarvis-key`.
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

## Säkerhetsbeteende

- 400: ogiltigt schema, URL-parametrar eller klientstyrd destination
- 401: saknad eller felaktig endpointnyckel
- 405: fel metod (t.ex. GET)
- 413/415: för stort anrop respektive fel Content-Type
- 423: autonomin är pausad (ingen dispatch)
- 503: backendkonfiguration eller autonomistatus kan inte verifieras (ingen avsiktlig dispatch)
- 502: GitHub avvisade dispatch
- 202: JSON-uppdrag accepterat av GitHub (inte bevisat slutfört)

GitHub kan ha accepterat ett uppdrag precis innan timeout; **gör inte blinda omförsök**.
Ingen upstream-feltext, nyckel eller intern serverrespons ska returneras till klienten.

## Kontroll före release

1. Migrera alla gamla Comet-klienter från `GET ?k=` till POST + header. Lista och testa varje klient.
2. Rotera `JARVIS_ENDPOINT_KEY` om den förekommit i URL:er/loggar.
3. Kör det nyckelfria CI-testet, därefter staging med giltig nyckel och negativtester.
4. Verifiera `SUPABASE_SECRET_KEY` (endast server-side). Fallback till legacy JWT får endast ha `role=service_role`.
5. Verifiera pausad autonomi, fel tenant/destination, fel metod och normal dispatch genom GitHub run-ID.
6. Bekräfta Supabase Edge Function JWT-inställning, CORS-klienter och legitim användarupplevelse.
7. Release kräver separat godkännande, dokumenterad rollback och efterföljande livekontroll.

Inga database-migrationer, prod-secrets eller produktionsdeployment omfattas av denna PR.
