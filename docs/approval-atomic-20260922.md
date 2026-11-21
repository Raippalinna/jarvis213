# Approval Center: atomisk granskningsbegäran

## Slutsats och leveransstatus

FÖRBERETT och TESTAT LOKALT. Kandidaten ersätter tre separata REST-skrivningar
med en databastransaktion och en beständig återförsöksnyckel. Detta är inte en
autentiserad mänsklig godkännandekedja och ger aldrig rätt att exekvera en åtgärd.
Arbetet hör till befintlig
[utvecklings-PR 2](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/2).

Ingen SQL i detta ändringspaket har körts i produktion. Main, produktionspolicyer,
kill switch, DRY_RUN, betalningsinställningar och riktiga affärsåtgärder lämnas
orörda. En överhoppad godkännandefråga tolkas inte som godkännande.

## Ändrat

- `db/proposed/20260922_atomic_review.sql` skapar en versionsnamngiven serverfunktion
  och en kvittotabell. Beslut, granskningsbegäran, audit och kvitto sparas tillsammans
  eller inte alls. Ett fel rullas tillbaka; funktionen sväljer inga databasfel.
- Endast `service_role` får anropa funktionen. Den kontrollerar aktör, tenant,
  agenttyp, indata och exakt ett textvärde `true` för `autonomy_enabled`.
  Den ändrar inte själva flaggan.
- Identisk tenant, aktör, session, uppgift, riskklass och orsak ger samma väntande
  kvitto, utan ny utgångstid. Ändrad uppgift eller ny session är en ny granskning.
  Återförsök vägrar beslut som ändrats, besvarats eller löpt ut.
- Servern använder transaktionslås och unik SHA-256-nyckel. Ett lokalt test bevisar
  identiska sekventiella återförsök, inte parallell drift med flera DB-sessioner.
- Python accepterar bara ett komplett, ej utgånget kvitto med `review_only`,
  `pending_approval` och `execution_authorized=false`. Ingen fallback till gamla
  separata skrivningar finns om RPC saknas eller nätverket ger fel.
- Timeout kan betyda att transaktionen sparats men svaret tappats. Statusen säger
  därför att kvitto saknas, inte säkert att inga rader finns. Ett återförsök måste
  använda samma session och samma innehåll.
- GitHub-omkörningar använder stabilt `GITHUB_RUN_ID`, inte `GITHUB_RUN_ATTEMPT`.
  `JARVIS_SESSION_ID` kan anges av en betrodd anropare och har företräde.
  Ny fristående körning skapar avsiktligt en ny granskningsidentitet.
- Nätverksfel loggas utan svarskropp. Uppgift och orsak redigeras för kända
  hemlighetsmönster före överföring. Det är inte fullständig persondataanonymisering.

## Testbevis och begränsningar

Lokalt passerade **87 Python-tester och 22 PGlite-databastester**. GitHub-flödet
har uppdaterats för att köra båda sviterna utan produktionsnycklar; dess resultat
måste kontrolleras för den aktuella committen innan CI rapporteras som godkänd.

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -v
npm ci --prefix tests/sql
npm test --prefix tests/sql
git diff --check
```

Databastesterna exekverar SQL-funktionen i en lokal PostgreSQL-baserad motor,
med syntetiska identiteter och ett minimalt schema. De täcker rollback vid fel
i request-, audit- och kvittoskrivning, återförsök, nekade klientroller,
avstängd/saknad/dubbel kill switch, fel tenant, fel aktörstyp, ogiltig indata,
utgångstid, ändrade rader och SQL-liknande text som data.

Python-testerna täcker klientkvittot, trasiga och tomma svar, timeout,
ingen skrivfallback, ingen exekvering vid halt, redigering av hemligheter och
stabilt sessions-ID vid omkörning. Python kördes lokalt med 3.14, som ger en
Pydantic V1-kompatibilitetsvarning; GitHub-flödet använder Python 3.11.

Testerna bevisar inte produktionsschema, PostgREST-behörigheter, parallelism över
flera databasanslutningar, dashboard-inloggning, mänsklig godkännaridentitet eller
engångsexekvering. PGlite-fixturen är inte en produktionsmigrering.

## Förutsättningar och ordning före drift

1. Slutför den tidigare stoppade GitHub-identitetskontrollen och verifiera att
   [rätt secret](https://github.com/rickyraippalinna/jarvis-omega-v2/settings/secrets/actions/SUPABASE_SERVICE_ROLE_KEY)
   faktiskt sparats. Senast kontrollerade ändringsdatum var fortfarande
   2026-08-29T13:19:41Z; nyckelbyte är inte verifierat.
2. Inhämta uttryckligt godkännande för den separat förberedda borttagningen av
   sex osäkra klientpolicyer. Den nya serverfunktionen stänger inte den gamla
   direkta klientåtkomsten. Anonym direktåtkomst får inte återöppnas som reservväg.
3. Läs om produktionsschema och grants före eventuell migrering.
   `SELECT FOR SHARE` kräver UPDATE-rättighet på lästa låsta tabeller. Kandidaten
   förutsätter befintlig service-role-åtkomst till `system_config`,
   `approval_decision` och `approval_request`; den utökar inte deras grants.
4. Efter separat godkänd driftsättning: applicera serverkandidaten först och gör
   ett godkänt syntetiskt test, inklusive två parallella DB-sessioner och avbrutet
   HTTP-svar. Bekräfta radinnehåll och audit, inte bara grön körning.
5. Promovera klientkoden först när serverkontraktet verifierats och grenens
   övriga releasekrav är uppfyllda. Saknad RPC gör annars klienten stoppad.
6. Bygg och testa autentiserad mänsklig granskning och typade åtgärder bundna till
   exakt mottagare, payload, utgångstid och engångsexekvering separat. Ett
   statusbyte i en databasrad är fortfarande inte en säker godkännaridentitet.

Produktionsmålet är det befintliga
[JARVIS Prime-projektet](https://supabase.com/dashboard/project/fzmnqvmfilqizzftphbt),
inte en ny databas eller dashboard.

## Återställning

Före drift kan ändringen revertas på utvecklingsgrenen utan produktionspåverkan.
Efter drift ska en incident stoppas via befintliga godkända driftspärrar och
undersökas. Radera inte kvittotabellen eller audit som automatisk rollback.
Återgå inte blint till gamla separata INSERT eller anonyma policyer; bevara data
och förbered en granskad korrigering. Ingen automatisk återställning exekveras här.
