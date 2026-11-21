# P1 #73 – skrivskyddad incidenttriage för tidigare anonym dashboardåtkomst

Datum: 2026-11-14. Status: FÖRBERETT, inte driftverifierat.

## Känd evidens (enligt issue #73, inte omtestad i denna ändring)
- Före RLS-låsningen kunde syntetisk anon-roll läsa 13/13 rader ur `public.jarvis_dashboard` och 24/24 ur `public.jarvis_dashboard_v2`.
- Efter åtgärden är direkta anon/authenticated-grants återkallade och 37 rader bevarade.
- Ingen verifierad exfiltration. Avsaknad av träffar i ett begränsat loggfönster bevisar inte avsaknad av historisk åtkomst.
- Detta dokument ändrar inte databasen eller policyn.

## Säker beslutsordning
1. **Dataklassning:** Behörig datägare granskar schema/fälttyper via auktoriserad skrivskyddad kanal. Dokumentera endast fältnamn, klassning (offentlig/intern/personuppgift/sekretess) och granskarens datum; lägg aldrig radvärden, tokens eller personuppgifter i GitHub.
2. **Exponeringsfönster:** Fastställ från migrationernas verkliga tidsstämplar när de öppna policyerna infördes och stängdes. Om starttid saknas: ange okänd, inte uppskattad.
3. **Loggspår:** Undersök endast redan tillgängliga, behöriga API-/gateway-/databasloggar inom respektive retention. Registrera källa, täckningsperiod, sökvillkor och begränsningar. Loggar får inte kopieras till repo.
4. **Klientberoenden:** Inventera gamla frontend-anrop som gör direkt SELECT med anon/authenticated. Kontrollera med statisk kodsökning och testkonto; återinför inte öppna RLS-regler för kompatibilitet.
5. **Incidentbeslut:** Datägare/säkerhetsansvarig avgör dokumenterat om incident, registrerades rättigheter och eventuell GDPR-bedömning krävs. Undvik slutsats om dataläckage utan underlag.
6. **Avslut:** Stäng #73 först när dataklassning, loggtäckning, klientkontroll och ansvarigt beslut finns med verifierbara referenser i ett skyddat incidentregister.

## Verifieringsmatris
| Kontroll | Godkänt endast när | Nu |
|---|---|---|
| RLS efter låsning | Auktoriserat negativt anon/authenticated-test, positivt server-test | Tidigare rapporterat i #73; ej omtestat |
| Historisk åtkomst | Tillgängliga loggar granskade med dokumenterad retention | EJ VERIFIERAT |
| Dataklassning | Behörig ägare har godkänt fältklassning | EJ VERIFIERAT |
| Frontendkompatibilitet | Test av äldre klienter mot skyddat API | EJ VERIFIERAT |
| Incidentutfall | Signerat beslut i skyddad kanal | EJ VERIFIERAT |

## 0 kr – rangordnade vägar
A. Befintlig GitHub-kodgranskning och redan behörig Supabase read-only logg-/schemavy. Ingen ny kredit; åtkomst till loggar måste kontrolleras.
B. Separat branch med offline regressionstester för klientens API-anrop, utan produktionsnycklar eller Lovable.
C. Lokal open-source analys av **redan godkänt och avidentifierat** loggutdrag, om sådant finns. Ingen ny tjänst eller provperiod.

## Återställning
Stäng PR utan merge; ingen produktionsfunktion påverkas.

## Begränsning
Denna runbook är en triageförberedelse, inte bevis för att historiska data har lästs eller att incidenten är avslutad. Inga externa utskick, nyckelanrop, databasändringar eller driftsättningar utförs.
