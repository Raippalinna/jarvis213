# Sista anslutningskontrollen för Comet och Hugging Face

## Status

Förberett och testat lokalt, inte driftsatt. Den här lilla ändringen utgår
från produktionens main-commit
`e177f8fbfacedb85bc8cb6522a33fb5de5021ec9`, inte från den större reliability-PR:en
([produktionsbas](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/e177f8fbfacedb85bc8cb6522a33fb5de5021ec9)).

Nyckelbytet är redan klart och autentisering har verifierats med HTTP 200 för
rätt nyckel och HTTP 401 utan nyckel. Den här kontrollen behövs enbart för den
ännu oprövade kedjan från Jarvis-bryggan till GitHub och vidare till Hugging Face
([sparad anslutningsstatus](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/improvement/jarvis-reliability-20260920/docs/comet-huggingface-20260922.md)).

## Exakt ändring

- **Supabase:** lägg till en separat `verify_connection`-åtgärd i befintliga
  `jarvis-comet`, projekt `fzmnqvmfilqizzftphbt`. Den kräver autentiserad POST med
  nyckeln i `x-jarvis-key`, enbart två tillåtna JSON-fält och inga URL-parametrar.
- **Stoppregel:** läs enbart `system_config.autonomy_enabled` innan GitHub-anropet.
  Falskt, saknat, feltolkat eller oläsbart värde stoppar kontrollen. Flaggan ändras inte.
- **GitHub:** lägg till `jarvis-connection-check.yml` och två fristående
  kontrollskript i befintliga `rickyraippalinna/jarvis-omega-v2`. Jobbet har endast
  läsrättighet till kod och får HF_TOKEN, inte Supabase-, Notion-, Slack- eller
  modellleverantörernas övriga nycklar.
- **Hugging Face:** gör enbart GET till kontoidentiteten och den offentliga
  modellkatalogen, med samma tidigare verifierade kontrollskript.
- **Oförändrat:** ordinarie Jarvis-jobb, cron-scheman, modellval, minnesskrivningar,
  notifieringar, abonnemang, saldo och automatisk påfyllning. Den större PR:en
  slås inte samman.

De ordinarie kodvägarna i Edge Function är bevarade; endast det nya reserverade
fältet `action` leder till den separata kontrollen. Den ordinarie körningens
tidigare säkerhetsbrister löses inte av denna avgränsade ändring och inget
vanligt Jarvis-uppdrag används som test.

## Den enda planerade provbegäran

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

Bryggans enda skrivande anrop skapar följande kontrollhändelse i
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

Det tidigare nyckelgodkännandet omfattade inga GitHub-jobb. Därför får denna
produktionsändring och en enda kontrollhändelse inte genomföras förrän användaren
har godkänt just detta paket.

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

Efter godkännande: kontrollera att main och Edge Function fortfarande har rätt
bas, publicera endast den här isolerade ändringen, läs tillbaka sparad kod,
kontrollera stoppregeln, skicka provbegäran en gång och följ enbart jobbet med
det angivna kontroll-ID:t. HTTP 202 betyder accepterad dispatch, inte godkänd
Hugging Face-kontroll; det senare kräver lyckat jobb och dess sanerade resultat.
Vid ett tvetydigt timeoutfel ska ingen automatisk omkörning göras.

Ett lyckat resultat verifierar anslutningskedjan och kontoåtkomsten. Det bevisar
inte betald inferens, modellkvalitet, en vanlig Jarvis-körning eller att Hugging
Face har blivit ordinarie modellleverantör; sådana ändringar ingår inte.

## Återställning

Originalet för Edge Function finns i `tests/fixtures/jarvis_comet_v6.ts`, med
kod-SHA-256
`00ae20b8e39d2550fe336a424794c57f45b6c2be13cb28618c6cd62e436fe40c`.
Om den nya kontrollvägen misslyckas återställs samma originalkod och enbart
kontrollpaketets GitHub-commit återställs. Inga hemligheter, databastabeller,
modellrutter eller betalningsinställningar ska ändras som återställning.
