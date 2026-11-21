# Jarvis: nästa kvalitetstest med Qwen3-235B

Status: **VERIFIERAT I DRIFT FÖR ENGÅNGSPROVET; INNEHÅLL GODKÄNT**.
Användaren godkände exakt detta prov 2026-09-23 kl. 08:25 CEST.
Det genomfördes kl. 12:28 CEST efter att Comet åter var tillgänglig
([körningskvittot](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)).
Vanliga HF-uppdrag aktiverades inte. Ett godkänt syntetiskt exempel är inte
ett generellt kvalitetsmått eller ett nytt tillstånd att skicka verksamhetsdata.

## Verifierat genomförande

- **Kod och körning:** commit
  `f0077eb1579278f15afb7fa341c7c3de2aaf1b1b` driftsattes på `main`.
  Körning `35848987272` slutfördes med `success`, körnummer 1, försök 1,
  exakt ett anropsförsök och ett mottaget svar
  ([GitHub-kvittot](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)).
- **Faktisk användning:** 155 indatatoken, 82 utdatatoken och 237 totalt.
  Rapporterade token gånger katalogpriserna gav 0,0000802 USD; detta är
  en beräkning, inte en slutfaktura
  ([svars- och användningsloggen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)).
- **Registrerad användning hos HF:** efter körningen visades en begäran
  för Qwen3-235B och upplupen kostnad **< 0,01 USD**.
  Raden för det äldre Qwen3-4B-provet visade fortfarande en begäran,
  nu också med **< 0,01 USD**
  ([HF:s användningsöversikt](https://huggingface.co/settings/inference-providers/overview)).
- **Kvalitet:** samtliga fem förutbestämda innehållskriterier godkändes
  manuellt. Det centrala tidigare felet återkom inte: svaret anger uttryckligen
  ”Kontrollera underlaget” och därefter ”Föreslå startdatum”
  ([modellsvaret](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)).
- **Avgränsning:** ingen omkörning, fallback, normal HF-routing, ny
  betalningsinställning eller minnesskrivning från modellen genomfördes.
  Körningsrapporten anger `normal_jarvis_routing_changed: false`
  ([provloggen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)).

Resultatuppdateringen sparas endast på förberedelsegrenen. Produktionskodens
godkända commit och det redan förbrukade engångsjobbet ändras inte.

## Jämförelsens upplägg

Endast modellen byttes i samma syntetiska begäran: från
`Qwen/Qwen3-4B-Instruct-2507:nscale` till
`Qwen/Qwen3-235B-A22B-Instruct-2507:nscale`. Nscale, båda meddelandena,
JSON-formatet, temperatur 0 och gränsen 180 utdatatoken behölls oförändrade.
Det gör jämförelsen mer avgränsad än att samtidigt ändra instruktionen.
Ingen svarsupprepning eller statistisk slutsats ingår.

Den tidigare körningen fick tekniskt svar men ändrade kontrollobjektet:
”Kontrollera materialet enligt underlaget” i stället för att kontrollera
underlaget. Även sammanfattningen kopplade kontrollen till materialet
([tidigare körning](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35788384466)).
Det nya provet utformades för att upptäcka detta betydelsefel, inte bara kontrollera
att API-anropet och JSON-formatet fungerar.

Modellkortet beskriver 235 miljarder parametrar, varav 22 miljarder aktiveras,
och endast icke-resonerande läge. Kortet fastställer inte modellens kvalitet
på svenska eller på detta uppdrag
([Qwens modellkort](https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507)).
Storlek och leverantörens allmänna kvalitetsanspråk är inte ett testresultat.

## Exakt mottagare och begäran

Den godkända destinationen var en enda POST till
[Hugging Face Chat Completions](https://router.huggingface.co/v1/chat/completions),
uttryckligen routad till Nscale. Leverantörssuffixet beskrivs i
[Nscales HF-dokumentation](https://huggingface.co/docs/inference-providers/en/providers/nscale).
Data går till Hugging Face och Nscale; inga garantier om svensk datalagring,
lagringstid eller träningsanvändning antas.

Hela innehållet som skickades visas nedan. Endast denna fiktiva text
ingår, inga kunduppgifter, dokument, Jarvis-minnen, personuppgifter,
verktygsanrop eller tidigare modellresultat.

```json
{
  "model": "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale",
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

## Faktiskt modellsvar

Följande är det fullständiga JSON-svaret från modellen, avkodat från
[körningsloggen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272).
Det är modellen själv som producerade formuleringarna; bedömningsstödet
längre ned skickades inte med.

```json
{
  "sammanfattning": "Projekt Alfa har tagit emot det levererade materialet. Underlaget måste kontrolleras innan arbetet kan påbörjas, och ett startdatum ska föreslås efter kontrollen.",
  "nasta_steg": [
    "Kontrollera underlaget",
    "Föreslå startdatum"
  ]
}
```

## Förutbestämd kvalitetsgranskning

Teknisk kvittens och innehållskvalitet rapporteras separat.
Varje kriterium bedöms manuellt mot originaltexten som GODKÄNT, UNDERKÄNT
eller OKLART, med ett kort citat ur det faktiska svaret som bevis.
Kontrollanten får inte godkänna genom enbart nyckelordsräkning eller genom
att förlita sig på att GitHub-jobbet blev grönt.

| Kriterium | Krav för GODKÄNT | Nytt resultat |
|---|---|---|
| Leveransstatus | Materialet har redan levererats till Projekt Alfa. Ingen utförd kontroll eller arbetsstart påstås. | GODKÄNT: ”har tagit emot det levererade materialet” ([modellsvaret](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)). |
| Kontrollobjekt | Både sammanfattning och steglista bevarar att underlaget ska kontrolleras. Materialet får inte ersätta underlaget som kontrollobjekt. Otydlig syftning räknas som OKLART. | GODKÄNT: ”Underlaget måste kontrolleras” och ”Kontrollera underlaget” ([modellsvaret](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)). |
| Ordning och handling | Först kontroll av underlaget före arbetsstart, därefter förslag till startdatum. Ett förslag får inte omvandlas till ett fastställt datum eller faktisk arbetsstart. | GODKÄNT: ”innan arbetet kan påbörjas” och ”ett startdatum ska föreslås efter kontrollen”; steglistan följer samma ordning ([modellsvaret](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)). |
| Faktatrohet | Inga nya datum, personer, kvalitetsbrister, beslut, godkännanden eller andra sakuppgifter tillförs. | GODKÄNT: sammanfattningen och båda stegen håller sig till originaltextens leverans, underlagskontroll och datumförslag ([fullständiga svaret](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)). |
| Språk och format | Begriplig svenska, exakt JSON-nycklarna `sammanfattning` och `nasta_steg`, två icke-tomma steg, inga extra fält, kodblock eller avklippning. | GODKÄNT: komplett svensk JSON med exakt de två fälten och två steg; körningens formatkontroll passerade ([svarsloggen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272)). |

Samlat innehållsresultat blir GODKÄNT endast om alla fem kriterier är
GODKÄNDA. Ett UNDERKÄNT ger UNDERKÄNT; annars ger kvarvarande osäkerhet
OKLART. Uteblivet, felaktigt eller avklippt tekniskt svar redovisas som
TEKNISKT MISSLYCKAT, inte som ett bedömbart kvalitetssvar.

En godtagbar handlingsföljd är ”Kontrollera underlaget innan arbetet startar”
och ”Föreslå därefter ett startdatum”. Detta är bedömningsstöd, inte
ytterligare text som skickas till modellen.
Ett godkänt exempel bevisar inte generell svensk kvalitet och ger inget
nytt numeriskt kvalitetspoäng för produktionsroutern.

## Kostnad och begränsningar

Den offentliga katalogen kontrollerades på nytt 2026-09-23 kl. 10:26:45 UTC
(12:26:45 CEST). Den exakta rutten var då `live`, med stöd för strukturerat
svar, 32 768 tokens kontext och priserna 0,20 USD per miljon indatatoken
samt 0,60 USD per miljon utdatatoken
([HF:s modellkatalog](https://router.huggingface.co/v1/models);
[prisernas enhet](https://huggingface.co/docs/inference-providers/en/hub-api)).
Detta är en daterad observation, inte en garanti om framtida tillgänglighet.

Med räkneunderlaget 2 048 indatatoken och högst 180 utdatatoken blir den
beräknade kostnaden `(2048 × 0,20 + 180 × 0,60) / 1 000 000` =
**0,0005176 USD**. Godkänd beräkningsgräns var **0,01 USD**.
Med det uttryckliga räkneantagandet 15 kr/USD motsvarar gränsen 0,15 kr;
15 kr/USD är inte en verifierad aktuell växelkurs.
Tokenantal och katalogpris ger inte ett leverantörsgaranterat fakturatak.

Vid det tidigare provet skilde sig tokenberäkningen 0,00000431 USD från
HF-översiktens visade upplupna kostnad 0,01 USD. Ingen viss avrundningsregel
eller slutlig faktura har antagits
([sparad resultatredovisning](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/60b7a6f74a80f1815654315989746f06838f56c8/docs/huggingface-pilot-20260922.md)).
Vid den nya kontrollen efter Qwen3-235B-provet visade HF däremot
**< 0,01 USD för vardera modellen**, vilket redovisas ovan.
Tidigare och senare visningar hålls isär; ingen av dem gör tokenberäkningen
till en verifierad slutdebitering.

Före start visade betalningssidan 12,00 USD i krediter och avstängd automatisk
påfyllning; inga betalningsinställningar ändrades
([betalningssidan](https://huggingface.co/settings/billing)).
Nscale var aktiverat med `Using HF routing infrastructure` och utan egen
leverantörsnyckel
([providersidan](https://huggingface.co/settings/inference-providers/settings)).

- **Pris- och modellspärr:** läs katalogen igen precis före anropet och stoppa
  vid saknad exakt rutt, högre pris, inaktiv leverantör eller bristande
  JSON-stöd. Ingen annan modell eller leverantör väljs automatiskt.
- **Ett försök:** endast första manuella körningen och första försöket av
  detta daterade jobb får skicka begäran. Fel, timeout och avbrott ger ingen
  omkörning, fallback eller nytt godkännande på automatik.
- **Befintlig nyckel:** endast befintlig GitHub-hemlighet `HF_TOKEN` lämnas
  till provsteget. Checkout har GitHubs vanliga lästoken; inga andra
  tjänstenycklar lämnas till jobbet.
- **Ingen betalningsändring:** inget nytt kreditköp, ingen automatisk
  påfyllning och inga ändringar av abonnemang eller kontots budgettak.
  Kontrollera i webbläsaren att Nscale fortfarande använder HF-routad
  debitering och att automatisk påfyllning är avstängd före eventuell start
  ([HF:s debiteringsbeskrivning](https://huggingface.co/docs/inference-providers/en/pricing)).
- **Stoppregel:** kontrollanten läser
  `public.system_config.autonomy_enabled` i Supabase-projekt
  `fzmnqvmfilqizzftphbt` omedelbart före start. Bara verifierat sant tillåter
  start; ett saknat värde eller läsfel stoppar. Jobbet kräver kontrolltid
  högst fem minuter gammal. Detta är en startkontroll, inte fortlöpande
  övervakning, och värdet får inte ändras för att genomföra provet.
- **Teknisk tidsgräns:** HTTP-anropet har 25 sekunders timeout och jobbet
  högst två minuter. Ett avbrott efter att begäran påbörjats kan ändå
  medföra debitering; en osäker utgång får inte föranleda ett nytt försök.

## Driftsatt paket och genomförd start

Mål är befintliga privata
[Jarvis-repot](https://github.com/rickyraippalinna/jarvis-omega-v2), med
[main f0e2e1a](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/f0e2e1a3fa6c82179ceca89336a2214ae8ff93df)
som bas. Följande fyra filer tillfördes av den separat granskade och
godkända [commit f0077eb](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/f0077eb1579278f15afb7fa341c7c3de2aaf1b1b):

- `.github/workflows/huggingface-quality-20260923.yml`
- `scripts/huggingface_quality_20260923.py`
- `tests/test_huggingface_quality_20260923.py`
- `docs/huggingface-quality-20260923.md`

Inget befintligt produktionsjobb, Supabase-funktion, schema, modellprofil
eller minnesflöde ändras. Den större
[PR 2](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/2) ingår inte.
Det gamla engångsprovet återanvänds inte och dess filer lämnas orörda.

Godkännandet lämnades kl. 08:25 CEST. När Comet inte kunde nås gjordes
ingen driftsättning eller inferens. Efter användarens klartecken kl. 12:25
kunde betalnings- och providerinställningarna åter verifieras.
Den granskade basen jämfördes på nytt före driftsättning och samtliga fyra
filer lästes tillbaka byte-identiska från `main`.

Stoppregeln lästes som sant kl. 10:27:52.202203 UTC omedelbart före start.
Detta var en faktisk förkontroll via Supabase, inte ett antaget permanent
tillstånd eller fortlöpande övervakning. Därefter gjordes endast följande
manuella start av `huggingface-quality-20260923.yml`:

```json
{
  "approval": "HF-QUALITY-20260923-QWEN235B-NSCALE",
  "approved_sha": "f0077eb1579278f15afb7fa341c7c3de2aaf1b1b",
  "guard_checked_at": "2026-09-23T10:27:52.202203Z"
}
```

Körningen skapades kl. 10:28:25 UTC och var slutförd kl. 10:28:41 UTC.
Jobbet och HF:s modellöversikt bekräftar vardera ett nytt prov; ingen
andra start eller omkörning gjordes
([GitHub-kvittot](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35848987272);
[HF:s användningsöversikt](https://huggingface.co/settings/inference-providers/overview)).
Detta engångsprov är nu förbrukat. Ny modellkörning eller aktivering av
vanliga HF-uppdrag ingår inte i godkännandet.

## Lokal verifiering och återställning

Testerna körs helt offline med syntetiska svar och utan riktiga nycklar.
De granskar rätt kontext och commit, omkörningsspärr, färsk kontrolltid,
prishöjning, kontoavvikelse, tomt eller avklippt svar, känslig svarstext,
timeout, avbrott och frånvaro av fallback.
De kontrollerar också att dokumentets payload matchar koden och att
enda payloadändringen jämfört med första provet är modellens namn.

Ett regressionstest matar in det tidigare betydelsefelet och kontrollerar
att korrekt JSON aldrig blir ett automatiskt semantiskt godkännande.
Testet bedömer inte språkförståelse; den femdelade granskningen görs efter
ett eventuellt verkligt modellsvar.

```text
python -m unittest discover -s tests -p 'test_*.py'
```

Samtliga 46 lokala tester passerade 2026-09-23: 13 testmetoder för det nya
paketet och 33 befintliga regressionstester. Inga modellanrop eller riktiga
hemligheter användes. Inget lokalt mocktest är ett bevis på den nya
modellens verkliga svarskvalitet.
Återställning av driftsättningen innebär att återställa
enbart denna additiva commit. Inga nycklar, betalningsinställningar eller
befintliga tjänster ska ändras och ingen modellkörning görs automatiskt.
