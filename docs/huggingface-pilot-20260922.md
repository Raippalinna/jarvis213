# Jarvis: avgränsat Hugging Face-prov

## Omfattning och status

Det avgränsade provet godkändes av användaren 2026-09-22 kl. 23:42 CEST och
genomfördes kl. 23:44 CEST. Teknisk status: **VERIFIERAT I DRIFT** för just detta
engångsanrop. Innehållskontroll: **UNDERKÄND**; svaret ändrade kontrollobjektet
från underlaget till materialet
([körning och logg](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35788384466)).
Windows-genvägen är separat och har verifierats av användaren.

### Faktiskt resultat

- **Kod och körning:** exakt godkänd commit
  `f0e2e1a3fa6c82179ceca89336a2214ae8ff93df`, körning `35788384466`,
  körnummer 1, försök 1 och ett anropsförsök
  ([GitHub-kvittot](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35788384466)).
- **API-svar:** status `completion_received`, 155 indatatoken och 92
  utdatatoken; den begärda rutten var
  `Qwen/Qwen3-4B-Instruct-2507:nscale`
  ([svarsloggen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35788384466)).
- **Kvalitetsavvikelse:** första nästa steg blev exakt
  ”Kontrollera materialet enligt underlaget”, fast indata sade att underlaget
  skulle kontrolleras. Även sammanfattningen kopplade kontrollen till materialet,
  så ett tekniskt lyckat jobb räknas inte som ett godkänt innehållstest
  ([modellsvaret](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35788384466)).
- **Visad debitering:** HF:s kontoöversikt registrerade ett anrop till denna
  modell och visade 0,01 USD i upplupen kostnad. Detta är sidans visade belopp,
  inte ett påstående om en färdig slutfaktura
  ([HF:s användningsöversikt](https://huggingface.co/settings/inference-providers/overview)).
- **Beräkning, inte faktura:** rapporterade token gånger de kontrollerade
  katalogpriserna gav 0,00000431 USD. Det ersätter inte HF:s visade 0,01 USD;
  skillnaden har inte förklarats eller antagits vara en viss avrundningsregel
  ([beräkningsloggen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35788384466)).
- **Kvarstående gräns:** inga nya modellförsök, inga betalningsändringar och
  ingen aktivering av vanliga HF-uppdrag gjordes. Provet skapar inget
  kvalitetspoäng och motiverar inte att produktionsgränser sänks.

Resultatuppdateringen sparas enbart på förberedelsegrenen. Produktionskodens
godkända commit och övriga Jarvis-jobb ändras inte av denna dokumentation.

Den godkända ändringen lade endast till ett daterat, manuellt engångsjobb,
ett provskript, offline-tester och denna beskrivning i befintliga privata
[Jarvis-repot](https://github.com/rickyraippalinna/jarvis-omega-v2).
Basen är [main 5447661](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/5447661e92a9638bd23b158cc651ef0b4176fdad).
Den större [PR 2](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/2)
slås inte samman.

## Mottagare och data

En enda POST till
[Hugging Face Chat Completions](https://router.huggingface.co/v1/chat/completions)
med den uttryckliga rutten `Qwen/Qwen3-4B-Instruct-2507:nscale`. Denna modell
stöder endast icke-resonerande läge enligt
[modellkortet](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507);
providersuffixet stöds enligt
[Nscales HF-dokumentation](https://huggingface.co/docs/inference-providers/en/providers/nscale).
Svensk kvalitet är ännu oprövad och ska bedömas från svaret.

Endast följande två texter skickas. Inga kunduppgifter, dokument, Jarvis-minnen,
kontouppgifter eller externa verktyg bifogas.

```json
{
  "model": "Qwen/Qwen3-4B-Instruct-2507:nscale",
  "messages": [
    {
      "role": "system",
      "content": "Du är Jarvis testassistent. Använd endast texten i användarmeddelandet. Svara på svenska med exakt ett JSON-objekt utan kodblock och utan extra fält: sammanfattning (sträng), nasta_steg (lista med två strängar). Inga påhittade uppgifter."
    },
    {
      "role": "user",
      "content": "Fiktivt test: Projekt Alfa har fått materialet levererat. Underlaget ska kontrolleras innan arbetet startar. Efter kontrollen ska ett startdatum föreslås. Sammanfatta läget och ange nästa två steg i rätt ordning."
    }
  ],
  "max_tokens": 180,
  "temperature": 0,
  "n": 1,
  "stream": false,
  "response_format": {"type": "json_object"}
}
```

Texten går till Hugging Face och Nscale. Ingen garanti om lagringstid,
träningsanvändning eller svensk datalagring antas.

## Kostnad och kontroller

Den offentliga katalogen visade 2026-09-22 kl. 21:10 UTC priserna 0,01 USD per
miljon indatatoken och 0,03 USD per miljon utdatatoken för denna exakta rutt
([modellkatalogen](https://router.huggingface.co/v1/models);
[prisernas enhet](https://huggingface.co/docs/inference-providers/en/hub-api)).
Skriptet läser katalogen på nytt och stoppar vid högre priser, saknad rutt eller
ej aktiv leverantör.

Beräkningsunderlaget är konservativt 2 048 indatatoken och högst 180 utdatatoken,
vilket med dessa katalogpriser ger 0,00002588 USD. Testkoden stoppar om den
beräknade kostnaden överstiger 0,01 USD. Som uttryckligt räkneantagande, inte
aktuell valutakurs, används 15 kr/USD: beräkningsgränsen motsvarar då 0,15 kr.
Token- och katalogkontrollen är inte ett leverantörsgaranterat fakturatak.

Nscale var aktiverat med `Using HF routing infrastructure` och utan egen
leverantörsnyckel på
[kontots providersida](https://huggingface.co/settings/inference-providers/settings).
Betalningssidan visade vid kontrollen 12,00 USD i krediter och avstängd automatisk
påfyllning ([betalningssidan](https://huggingface.co/settings/billing)).
Kontoinställningarna ska läsas igen före körning, inte ändras.
HF-routad användning belastar HF-kontot enligt
[HF:s debiteringsbeskrivning](https://huggingface.co/docs/inference-providers/en/pricing).

- **Ingen betalningsändring:** inget nytt kreditköp, abonnemang, budgettak eller
  automatisk påfyllning ändras.
- **Ingen omkörning:** endast den första manuella körningen och första försöket
  får göra anropet. Fel, timeout och avbrott ger ingen retry eller fallback.
  Även ett misslyckat första försök förbrukar detta daterade prov.
- **Minsta åtkomst:** jobbet får befintlig `HF_TOKEN` endast i provsteget samt
  GitHubs normala lästoken för checkout. Det får inte Supabase-, Notion-, Slack-
  eller andra modellnycklar.
- **Stoppregel:** kontrollanten läser
  `public.system_config.autonomy_enabled` i Supabase-projekt
  `fzmnqvmfilqizzftphbt` omedelbart före manuell start. Endast verifierat sant
  tillåter start. Jobbet kräver en tidsstämplad kontroll högst fem minuter gammal.
  Detta är en kontroll före engångsstart, inte fortlöpande Supabase-övervakning.
- **Ingen produktionsaktivering:** normala jobb, scheman, Supabase-funktionen,
  modellprofil, kvalitetsgränser och minnesskrivningar ändras inte.

## Godkännandets omfattning och använd startbegäran

Godkännandet omfattade exakt kodversion, fyra tillagda filer på main och ett
enda angivet modellprov. Main och den sparade versionen kontrollerades före
start. HF-routad debitering och avstängd automatisk påfyllning verifierades i
webbläsaren. Stoppregeln lästes som sant kl. 21:43:55 UTC, varefter endast
`huggingface-pilot-20260922.yml` startades med följande indata:

```json
{
  "approval": "HF-PILOT-20260922-QWEN4B-NSCALE",
  "approved_sha": "f0e2e1a3fa6c82179ceca89336a2214ae8ff93df",
  "guard_checked_at": "2026-09-22T21:43:55Z"
}
```

GitHub Actions kan förbruka körminuter enligt kontots vanliga villkor.
Maximal jobbtid är två minuter. Gör inget nytt anrop om det första anropets
utfall är osäkert; en timeout efter påbörjad POST kan ändå ha debiterats.

## Verifiering och återställning

33 lokala offline-tester passerade: 11 testmetoder för detta prov och 22 för de
befintliga, oförändrade anslutningskontrollerna. Testerna täcker godkänd begäran,
nekad omkörning, felaktig kodversion, för gammal stoppregelkontroll, prisändring,
felaktigt konto, tomt eller avklippt svar, känslig svarstext, avbrott, utebliven
fallback samt att dokumentets payload exakt matchar kodens.
Ingen modell eller riktig hemlighet används i testerna.

Kör från repots rot:

```text
python -m unittest discover -s tests -p 'test_*.py'
```

Loggen ska visa exakt granskad commit, begärd rutt, ett anropsförsök, ett komplett
svar och rapporterat tokenantal. Granska att materialleveransen återges korrekt
och att de två nästa stegen är kontroll av underlag följt av förslag på
startdatum, utan nya påhittade sakuppgifter.

Godkänt prov bevisar bara att denna syntetiska begäran fungerade. Det ger inte
ett påhittat kvalitetspoäng, rätt att skicka känsliga uppgifter eller bevis för
vanliga Jarvis-uppdrag. Normal modellrouting förblir separat och avstängd.

Ändringen är helt additiv. Återställning innebär att återställa enbart detta
provpakets commit; inga nycklar, betalningsinställningar eller befintliga
produktionstjänster ska ändras. Ingen automatisk återställning eller ny
modellkörning görs efter fel.
