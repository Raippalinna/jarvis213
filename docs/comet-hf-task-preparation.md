# Comet och Hugging Face för vanliga Jarvis-uppdrag

Förberett den 22 september 2026 i befintligt `jarvis-omega-v2`. Leveransen är
en säker startinstruktion och en avstängd modellprofil, inte en produktionsstart.

## Leverans och avgränsning

- **Comet-start:** en granskningsbar prompt finns i
  [Comet-start för Jarvis](../clients/mobile/comet-start.md). Den öppnar det
  befintliga GitHub-arbetsflödets startformulär utan hemligheter i webbadressen
  och förbjuder automatisk start och automatiska återförsök.
- **Hugging Face:** `config/huggingface.json` levereras med `enabled: false`,
  tom modell/leverantör och utan påhittad kvalitetsmätning, valutakurs eller
  godkänt kostnadstak. `JARVIS_ENABLE_HUGGINGFACE` har standardvärdet `0`.
- **Vanliga uppdrag:** första profilen är textsammanfattning, prioritering och
  rutin-/kodutkast från material som uttryckligen lämnas i uppdraget. Den är
  inte en webbsökare, generell verktygsagent eller kunddokumentintegration.
- **Sparplats:** ändringarna hör till den befintliga utvecklingsgrenen
  `improvement/jarvis-reliability-20260920`. Den större säkerhetsändringen i
  [PR 2](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/2) är en
  kodförutsättning, inte något som denna förberedelse får slå ihop eller driftsätta.

Den tidigare verifierade anslutningskontrollen gällde bara autentisering,
GitHub-dispatch och HF:s identitet/katalog; den gjorde inga modellkörningar
([verifierad kontroll](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).
Den kontrollen har inte körts igen som del av denna förberedelse.

## Tekniska skydd

- **Uttryckligt val:** GitHub-formuläret får `provider=default|huggingface`.
  HF tillåts bara vid manuell `workflow_dispatch`, inte via scheman,
  `workflow_call` eller den äldre `repository_dispatch`-vägen.
- **En bestämd väg:** modell och underleverantör måste vara uttryckligen
  konfigurerade. Automatval som `fastest`, `cheapest`, `preferred` och `auto`
  nekas; en specifik leverantör kan väljas med `modell:leverantör`
  enligt [HF:s routningsdokumentation](https://huggingface.co/docs/inference-providers/en/index).
- **Aktuellt prisunderlag:** den offentliga katalogen läses utan token, med
  tidsgräns, storleksgräns och nekade omdirigeringar. Modellen måste finnas
  exakt en gång och den valda leverantören vara `live`, med angivet pris
  och kontextlängd; prisfälten är USD per miljon token enligt
  [HF:s katalogschema](https://huggingface.co/docs/inference-providers/en/hub-api).
- **Kostnadsgrind:** senaste katalog får vara högst 24 timmar gammal;
  betrott budgetunderlag högst en timme gammalt. Saknat, framtida eller
  ogiltigt underlag stoppar körning; okänd förbrukning blir aldrig noll.
- **Tokenram:** det avstängda exemplet föreslår högst 8 192 uppskattade
  inmatningstoken och 600 svarstoken. Svarslängden skickas som `max_tokens`;
  användning läses från `usage.prompt_tokens` och `usage.completion_tokens`
  enligt [HF:s chattschema](https://huggingface.co/docs/inference-providers/en/tasks/chat-completion).
- **Ingen reservmodell:** ett tomt, avklippt, filtrerat eller misslyckat svar
  leder till stopp efter det enda försöket. SDK-återförsök och HTTP-omdirigeringar
  är avstängda, och annan modell får inte väljas automatiskt.
- **Datagräns:** HF-profilen läser eller skriver inte privat minne, skapar inga
  godkännanderader, skickar inga Slack-aviseringar och levererar inte till Notion.
  R2/R3-klassade uppdrag och identifierade hemligheter stoppas; HF-tokenmönster
  ingår i befintlig maskering.
- **Nödstopp:** befintlig Supabase-spärr kontrolleras före körning och modellförsök.
  Workflow-koden för vidare befintliga `DRY_RUN`/`JARVIS_DRY_RUN`-variabler;
  inga spärrvärden ändras av förberedelsen.

Detta är en uppskattad kostnadsgrind, inte ett garanterat fakturatak.
Inmatningstoken uppskattas konservativt från UTF-8 och meddelanderamar, och
valutakursen är en uttrycklig beräkningsförutsättning, inte en hämtad marknadskurs.

Nuvarande `JARVIS_MONTH_SPEND_PCT` är inte en atomiskt uppdaterad månadsbokföring.
Flera uppdrag eller förbrukning utanför Jarvis kan därför ändra totalsumman;
denna version ska inte marknadsföras som obevakad månadsbudgetstyrning.

HF kan routa förfrågningar vidare till en underleverantör, och debiteringsväg
beror bland annat på om anropet använder HF-routning eller en separat
leverantörsnyckel enligt [HF:s faktureringsdokumentation](https://huggingface.co/docs/inference-providers/en/pricing).
Ingen sekretess-, lagrings- eller träningsgaranti antas för en ännu inte vald
leverantör; datagodkännande och faktisk faktureringsväg måste granskas före start.

## Vad som krävs före första riktiga uppdraget

1. Granska och godkänn exakt kodomfattning för produktion. Bevara det redan
   driftsatta isolerade anslutningstestet; slå inte ihop den större PR:n av misstag.
2. Välj en faktisk modell och specifik HF-leverantör från aktuell katalog.
   Granska datavillkor och använd uttryckligen godkänt, icke-känsligt material.
3. Dokumentera ett relevant kvalitetsunderlag. Profilen kräver en verklig
   kvalitetsbedömning och en hänvisning; katalogens tillgänglighet är inget
   kvalitetsbevis och testfixturernas siffror får aldrig kopieras till drift.
4. Besluta uppskattat kostnadstak per uppdrag och valutakursantagande. Tillför
   aktuell betrodd budgetandel samt dess kontrolltid, utan att nollställa den.
5. Granska `config/huggingface.json`, fyll i beslutade värden och aktivera först
   efter separat godkännande. Repo-flaggan `JARVIS_ENABLE_HUGGINGFACE=1` räcker
   inte ensam; konfigurationsfilen måste också vara komplett och godkänd.
6. Installera eller uppdatera den granskade Comet-genvägen utan nycklar, och
   verifiera enbart förhandsgranskningen i användarens inloggade webbläsare.
7. Godkänn ett enda pilotuppdrag med exakt text, kodversion, mottagande tjänster
   och kostnadsram. Verifiera sedan faktiskt resultat och förbrukning innan
   fler uppdrag eller vidare automation övervägs.

Betalda pilotanrop för modellutvärdering kräver eget godkännande och ska inte
kringgå kvalitetsgrinden genom en påhittad `quality_index`. Sparade tidigare
utvärderingar kan användas om de gäller den valda modellen och arbetsuppgiften.

## Resultat och operatörskontroll

Vid senare godkänd körning sparas `result.json` och `result.md` i det privata
GitHub-jobbets resultatarkiv. Därmed kan uppdrag och svar bli tillgängliga för
dem som har rättigheter i repot; lämna inte person- eller kunduppgifter i den
första profilen.

Kontrollera `status`, exakt modell med leverantörssuffix, svarsinnehåll,
tokenanvändning, `reserved_cost_sek`, `cost_is_estimate` och `unreconciled_cost`.
Det äldre fältnamnet `actual_cost_sek` innehåller fortfarande en beräkning, inte
ett avstämt fakturabelopp; vid timeout eller saknad tokenrapport är kostnaden
inte känd och ingen automatisk omkörning får göras.

Offlinekontroll från repots rot:

```bash
PYTHONPATH=src:. python -m unittest discover -s tests -v
npm ci --prefix tests/sql
npm test --prefix tests/sql
JARVIS_PROVIDER=huggingface JARVIS_ENABLE_HUGGINGFACE=0 \
  python scripts/huggingface_readiness.py
```

Sista kommandot ska rapportera `disabled`, `completion_requests: 0` och
`inference_tested: false`, med avslutskod 2 för ej körklart. Det är avsedd
spärrfunktion, inte ett skäl att ändra inställningar automatiskt.

## Genomförd lokal verifiering

Den färdiga kandidaten klarade 132 Pythonprov och 22 isolerade SQL-prov.
HF-proven använder syntetiska modellnamn, priser och kvalitetsvärden; hela
supervisorflödet provades också med det riktiga OpenAI-SDK:t mot en simulerad
HTTP-transport, aldrig mot en levande modellserver.

Proven omfattar lyckat svar, tomt svar, avklippt eller filtrerat svar, timeout,
saknad/felaktig tokenrapport, spärrad reservväg, nödstopp, DRY_RUN, känslig
inmatning, hemlighet i svar, föråldrat budgetunderlag och avsaknad av privata
minnes-/godkännandeskrivningar eller aviseringar. Lokal readiness rapporterade
`disabled` och avslutskod 2; ingen faktisk inferens verifierades.

Produktionsgrenen var vid avläsning oförändrad på
`5447661e92a9638bd23b158cc651ef0b4176fdad`, och PR 2 var fortsatt öppen.
De fyra kontrollerade repo-variablerna `JARVIS_ENABLE_HUGGINGFACE`,
`JARVIS_HF_BUDGET_CHECKED_AT`, `JARVIS_DRY_RUN` och `DRY_RUN` saknade
sparade värden; inga av dem skapades eller ändrades.

Detta resultat betyder TESTAT LOKALT och förberett för kodgranskning.
Det betyder inte DRIFTSATT, installerad Comet-genväg eller VERIFIERAD INFERENS.
Maskinläsbart underlag finns i
[förberedelsens testkvitto](evidence/comet-hf-task-preparation-20260922.json).

## Återställning

Ingen produktionsåterställning behövs för denna förberedelse eftersom den inte
driftsätts. Kodändringen kan återtas separat från basen
`47328f6e550e800b9f062edb2e06521bddcd0746` utan att röra nycklar eller billing.

Efter en framtida, separat godkänd aktivering är första stoppåtgärden att
inaktivera HF-profilen. En redan skickad modellbegäran kan fortfarande slutföras
och debiteras; ingen kreditering eller säker annullering utlovas.
