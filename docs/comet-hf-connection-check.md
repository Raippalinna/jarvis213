# Sista anslutningskontrollen för Comet och Hugging Face

## Slutstatus den 22 september 2026

**VERIFIERAT I DRIFT för den läsande anslutningskedjan.** Den enda godkända
provbegäran gick genom Jarvis-bryggan till GitHub och vidare till Hugging Face;
kontrollen slutfördes 20:16:50 svensk tid med resultatet `success`
([slutkontroll](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).

Endast det isolerade kontrollpaketet
`5447661e92a9638bd23b158cc651ef0b4176fdad` driftsattes på main; den större
reliability-PR:en är fortfarande öppen och inte sammanslagen
([driftsatt commit](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/5447661e92a9638bd23b158cc651ef0b4176fdad),
[separat PR](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/2)).

## Verifierade resultat

- **Computer till Jarvis:** den sparade `x-jarvis-key`-nyckeln autentiserar mot
  befintlig endpoint; tidigare kontroll gav HTTP 200 med nyckeln och HTTP 401
  utan nyckeln
  ([sparad anslutningsstatus](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/improvement/jarvis-reliability-20260920/docs/comet-huggingface-20260922.md)).
- **Supabase till GitHub:** exakt en POST accepterades med HTTP 202, och
  Supabase-loggen bekräftade version 7 vid 18:16:41.483 UTC; kontroll-ID:t
  återfanns i den avsedda GitHub-körningen
  ([Jarvis-endpoint](https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet),
  [korrelerad körning](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).
- **GitHub till Hugging Face:** det enda jobbet, `verify_connection`, verifierade
  kontot `rickyraippalinna` och läste en offentlig katalog med 137 modeller;
  resultatet var `identity_and_catalog_verified`
  ([jobbet och dess sanerade logg](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505/job/106875915162)).
- **Ingen modellkörning:** resultatet anger `completion_requests: 0`,
  `inference_tested: false` och `normal_jarvis_run: false`
  ([kontrollresultat](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505/job/106875915162)).
- **Återläst kod:** produktionsfunktionens version 7 jämfördes byte för byte
  med den godkända filen, med kod-SHA-256
  `e579d8656fad3859638d243686bb726a95f4d8226118a3aabe408fe8f5f39187`;
  den tidigare diagnostiken finns inte i den driftsatta koden
  ([godkänd kodversion](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/5447661e92a9638bd23b158cc651ef0b4176fdad)).

Det maskinläsbara driftresultatet finns i
`docs/evidence/connection-check-live-20260922.json` på denna dokumentationsgren.
Den tidigare lokala testfilen är bevarad som historiskt underlag, inte omskriven
så att lokala tester framstår som driftbevis.

## Exakt ändring

- **Supabase:** en separat `verify_connection`-åtgärd har lagts till i befintliga
  `jarvis-comet`, projekt `fzmnqvmfilqizzftphbt`. Den kräver autentiserad POST med
  nyckeln i `x-jarvis-key`, enbart två tillåtna JSON-fält och inga URL-parametrar.
- **Stoppregel:** koden läser enbart `system_config.autonomy_enabled` innan GitHub-anropet.
  Falskt, saknat, feltolkat eller oläsbart värde stoppar kontrollen. Flaggan ändras inte.
- **GitHub:** `jarvis-connection-check.yml` och två fristående
  kontrollskript har lagts till i befintliga `rickyraippalinna/jarvis-omega-v2`. Jobbet har endast
  läsrättighet till kod och får HF_TOKEN, inte Supabase-, Notion-, Slack- eller
  modellleverantörernas övriga nycklar.
- **Hugging Face:** kontrollen gör enbart GET till kontoidentiteten och den offentliga
  modellkatalogen, med samma tidigare verifierade kontrollskript.
- **Oförändrat:** ordinarie Jarvis-jobb, cron-scheman, modellval, minnesskrivningar,
  notifieringar, abonnemang, saldo och automatisk påfyllning. Den större PR:en
  slås inte samman.

De ordinarie kodvägarna i Edge Function är bevarade; endast det nya reserverade
fältet `action` leder till den separata kontrollen. Den ordinarie körningens
tidigare säkerhetsbrister löses inte av denna avgränsade ändring och inget
vanligt Jarvis-uppdrag används som test.

## Den enda genomförda provbegäran

Mottagare:
[befintlig Jarvis-endpoint](https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet).
Metod: POST. Content-Type: application/json. Autentisering: den redan sparade
nyckeln via säkert valv, utan att dess värde visas i en URL, logg eller rapport.

```json
{
  "action": "verify_connection",
  "check_id": "cc62340c-98bc-409b-9a40-6523e1eade84"
}
```

Bryggans enda skrivande anrop skapade följande kontrollhändelse i
[Jarvis-repot](https://github.com/rickyraippalinna/jarvis-omega-v2):

```json
{
  "event_type": "jarvis-connection-check",
  "client_payload": {
    "check_id": "cc62340c-98bc-409b-9a40-6523e1eade84"
  }
}
```

Det finns ingen fråga, kundtext, personuppgift eller Notion-destination i
testpayloaden. Jobbet startar inte `jarvis_cloud.py`, skickar inga meddelanden och
anropar ingen modell. GitHubs eventuella vanliga Actions-förbrukning är inte
kontrollerad här; inga Hugging Face-krediter ska förbrukas av identitets- eller
katalogkontrollen.

## Godkännande och verifiering

Användaren godkände uttryckligen detta isolerade paket och en enda kontroll
20:11 svensk tid den 22 september 2026. Ingen ytterligare provbegäran skickades,
och godkännandet användes inte för att starta ett vanligt Jarvis-uppdrag.

**45 lokala Edge-testfall och 22 Python-tester passerade.** Testerna omfattar
den oförändrade ordinarie koden, godkänd kontroll,
felaktig autentisering, tomma och felaktiga svar, stoppregel, avbruten begäran,
nekad dispatch, utebliven automatisk omkörning och skydd mot att känsliga
värden skrivs i resultatet. De använder enbart syntetiska testvärden och
nätverksstubbar, inte riktiga kontonycklar.

Testkommandon:

```text
python -m unittest discover -s tests -p 'test_*.py' -v
node tests/test_connection_check.mjs
```

Main och Edge Function kontrollerades mot rätt bas före driftsättning;
`system_config.autonomy_enabled` var `true` och ändrades inte. Efter driftsättning
lästes koden tillbaka, provbegäran skickades en gång och både serverloggen och
det korrelerade jobbets faktiska innehåll verifierades
([slutkontroll och resultat](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).

## Kvar utanför den godkända kontrollen

Hugging Face är inte aktiverad som modellleverantör för vanliga Jarvis-uppdrag;
ordinarie produktionsworkflow laddar fortfarande inte `HF_TOKEN`
([oförändrat ordinarie workflow](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/main/.github/workflows/jarvis-cloud.yml)).
Kontrollen bevisar därför inte betald inferens, modellkvalitet eller leverans av
ett vanligt uppdragsresultat till Notion
([testets uttryckliga avgränsning](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505/job/106875915162)).

En direkt `/jarvis`-genväg i Comet är inte konfigurerad eller verifierad av detta
headerbaserade Computer-test. Placera inte endpointnyckeln i ett bokmärke,
en webbadress eller en chatt
([separata anslutningsnivåer](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/improvement/jarvis-reliability-20260920/docs/comet-huggingface-20260922.md)).

## Återställning

Originalet för Edge Function finns i `tests/fixtures/jarvis_comet_v6.ts`, med
kod-SHA-256
`00ae20b8e39d2550fe336a424794c57f45b6c2be13cb28618c6cd62e436fe40c`.
Den godkända återställningen vid misslyckat sluttest avsåg samma originalkod och
enbart kontrollpaketets GitHub-commit; den behövde inte användas eftersom kontrollen
lyckades. Inga hemligheter, databastabeller,
modellrutter eller betalningsinställningar ska ändras som återställning.
