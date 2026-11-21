# Comet: säker autentisering och tenantgräns (2026-11-07)

Status: **Sparad säkerhetspatch i separat branch; inte mergad eller driftsatt.**

## Varför förändringen behövs

Den gamla `jarvis-comet`-funktionen accepterar en delad hemlighet via
`?k=<secret>` och låter klienten sätta `tenant`, `user_id` och `notion` i anropet.
Sådan metadata är **inte** ett bevis på identitet eller organisationsmedlemskap.
GET får inte utlösa kostnadsdrivande uppdrag. Normala uppdrag ska stoppas när
`system_config.autonomy_enabled` är falskt, saknas eller inte går att verifiera.

## Nytt requestkontrakt (owner only)

```http
POST /functions/v1/jarvis-comet HTTP/1.1
Content-Type: application/json
x-jarvis-key: <ägarspecifik hemlighet från godkänt hemlighetslager>

{"task":"Ge en kort statusrapport","tier":"LOW","fmt":"json"}
```

- Inga credentials, taskparametrar eller identiteter får anges i URL.
- Endast POST med JSON kan beställa ett uppdrag. OPTIONS är endast CORS-preflight.
- Task måste vara 1–4000 tecken utan kontrolltecken, tier FREE/LOW/MED/HIGH.
- Okända, dubbla och identitetsrelaterade fält avvisas.
- Ägarens tenant-id och Notion-destination är serverstyrda; detta är **inte**
  autentisering av flera användare eller kunder.
- Före dispatch läses `autonomy_enabled` via förväntad Supabase-origin. Endast
  exakt `true` tillåter körning, `false` ger 423 och allt okänt ger 503.
- GitHub `repository_dispatch` anses mottaget endast vid status 204.
  Uppströmsfeltexter, hemligheter och PAT returneras aldrig till anroparen.
- Transporten avvisar omdirigeringar och har tio sekunders timeout.
- Den isolerade `verify_connection`-åtgärden behåller eget avgränsat kontrakt;
  dess syntetiska tester körs fortsatt och får inte starta `jarvis-run`.

## Före produktionsrelease

1. Identifiera och uppdatera **alla** gamla klienter/bokmärken/Shortcuts och
   Comet-integrationer som fortfarande använder `?k=`, GET eller formulär.
2. Kontrollera att `JARVIS_ENDPOINT_KEY`, `JARVIS_GITHUB_PAT` och korrekt
   Supabase backendnyckel finns i serverns secret store utan att skriva ut värden.
3. Kör `node tests/test_connection_check.mjs` och
   `node --test tests/*.mjs` samt hela Python-sviten, utan live-nycklar.
4. Genomför separat testmiljötest med felaktig nyckel (401), GET (405),
   fel tenant/Notion (400), pausad autonomi (423), obekräftad autonomi (503),
   giltig request (202) och kontrollera förväntat GitHub-run-ID.
5. Efter klientmigrering och godkännande: deploya och verifiera faktisk drift.
   Rotera gamla endpointnyckeln om den förekommit i historik eller proxyloggar.

**Kända begränsningar:** delad endpointnyckel saknar användarspecifik identitet,
rate limits och strikt origin-allowlist. Inför extern/multi-tenant åtkomst krävs
Supabase Auth eller annan verifierad principal, tenant-medlemskap och testade RLS-regler.
Ingen förändring av kill switch eller Approval Center görs i patchen.

## Återställning

Före merge: stäng PR utan merge. Vid senare deploy kan tidigare Edge-version
återställas efter säkerhets- och klientgranskning; att slå på URL-credentials igen
är en säkerhetsregression och ska inte göras utan särskilt beslut.
