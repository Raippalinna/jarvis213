# Jarvis Intelligence: research och genomförd utbyggnad

Jarvis har fått en sparad utökning av sin befintliga projektskill och en lokalt testad kodutökning för behovsstyrd research, specialistplanering och granskning av förbättringsförslag. Det är förbättrade arbetsmetoder och verktyg, inte ändrade modellvikter, bevisad övermänsklig intelligens eller en aktiverad bakgrundssvärm.

Datum: 31 oktober 2026. Status: skill SPARAD och återläst; kod TESTAD LOKALT; ingen produktionssättning eller merge.

## Möjligheter

- **Selektiv specialisering:** En kontrollerad studie med 260 konfigurationer rapporterar att multiagentupplägg kan hjälpa uppdelningsbara uppgifter men försämra sekventiell planering; resultatet beror på hur samordningen passar uppgiften ([Kim m.fl., senaste versionen av studien](https://arxiv.org/abs/2512.08296)). För Jarvis väljer jag därför parallella, avgränsade researchspår när de är oberoende, men en ansvarig kodarm per sammanhängande ändring.
- **Bättre research, inte bara fler svar:** Anthropic beskriver en orkestrator med separata forskare och tydliga uppdragskontrakt, men också större tokenåtgång och begränsningar för uppgifter med mycket gemensam kontext ([Anthropics researchsystem](https://www.anthropic.com/research/multi-agent-research-system)). Min rekommendation är att mäta om de extra spåren hittar relevanta källor eller fel som en enklare väg missar.
- **Testbar självförbättring:** Darwin Gödel Machine visar forskningsresultat från ändring av agentkod med benchmarkåterkoppling, men rapporterar samtidigt försök att manipulera utvärderingsmålet ([Sakana AI](https://sakana.ai/dgm/)). För Jarvis betyder detta en spårbar kedja från observerat problem till kandidat, test, granskning och godkänt införande, inte fria omskrivningar av systemet.
- **Tvärvetenskap med ett syfte:** Matematik, fysik, psykologi, historia och filosofi kan ge olika sätt att pröva ett beslut. I den nya skillen måste varje lins ha en konkret fråga, nödvändigt underlag och ett kontrollerbart resultat; en ämnesetikett i en prompt räcker inte.

## Risker

- **Samordning kan försämra arbetet:** Det starkaste praktiska motargumentet är att uppdelning tappar outtalade beslut och gemensam kontext; Cognition argumenterar därför för enkla, sammanhängande agentflöden som utgångspunkt ([Cognition](https://cognition.ai/blog/dont-build-multi-agents)). Jag använder detta som skäl att begränsa parallellism, inte som ett universellt förbud mot flera agenter.
- **Källor kan bära skadliga instruktioner:** OWASP rekommenderar minsta behörighet, granskning av verktyg och beroenden samt skydd mot att externa instruktioner får styra agentens handlingar ([OWASP:s agent- och MCP-vägledning](https://owasp.github.io/DevSecOpsGuideline/2-Process/2-2-Develop/2-2-5-AI-Agent-and-MCP-Security/)). GitHub-adaptern läser därför bara metadata och exakta versioner, aldrig hämtade installskript eller repokod.
- **Fler verktyg är en större granskningsyta:** MCP:s säkerhetsvägledning behandlar bland annat tokenhantering, auktorisation och sessionsrisker; protokollet är inte i sig ett bevis på att en integration är säker ([MCP:s säkerhetsvägledning, draft](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)). Inga nya connectorbehörigheter har aktiverats i detta arbete.
- **Testresultat är inte affärsresultat:** Godkända enhetstester visar beteendet i de testade fallen. De visar inte att Jarvis tjänar mer pengar, fattar bättre strategiska beslut eller motstår alla framtida attacker.

## Dolda risker

- **Falsk källoberoende:** Två artiklar kan återge samma ursprung, och flera modeller kan upprepa samma fel. Den nya strukturella kontrollen räknar normaliserade ursprung och URL:er, men kan inte själv bevisa att ursprungsmärkningen är sann.
- **Självattesterade bevis:** En agent kan skriva `supported`, `PASS` eller en hash utan att underlaget verkligen har kontrollerats. Kodens granskningskontrakt validerar fälten och jämförelsen, inte granskarens identitet eller testloggens autenticitet; detta är uttryckligen dokumenterat.
- **En lyckad hämtning kan gälla gammalt innehåll:** Observationstid och publiceringsdatum är olika saker. Koden kontrollerar hämtningstidens form och ålder; innehållets aktualitet måste fortfarande bedömas för den aktuella frågan.
- **Baslinjen kan vara för enkel:** En kandidat kan se bättre ut bara för att den får fler försök, mer kontext eller svårare modell. En verklig kvalitetsjämförelse måste därför använda samma uppgifter och jämförbara resurser.
- **Överföring mellan domäner kan bli falsk precision:** Ett forskningsresultat från en benchmark, vårdekonomi eller historisk kris är inte automatiskt ett mått för Jarvis eller BTF. Rapporten skiljer därför forskningsfynd från mina designval och från det som faktiskt har körts.

## Hävstång

Den viktigaste flaskhalsen är min bedömning att det ännu saknas en uppgiftsspecifik kvalitetsmätning för hela Jarvis-kedjan, inte ett tillräckligt imponerande antal agentnamn. Den första hävstången är att göra fel, förbättringar och beslutsunderlag jämförbara innan fler komponenter aktiveras.

### Tvärvetenskaplig användning

| Område | Konkret användning i Jarvis | Krav och gräns |
|---|---|---|
| Matematik och statistik | Kontrollera beräkningar, enheter, basfrekvenser och känslighet. | Faktiska data eller tydligt märkta antaganden; inga fabricerade procentsatser. |
| Kausal analys | Skilja ”detta samvarierar” från ”den här åtgärden orsakar utfallet”; kausala slutsatser behöver antaganden utöver enbart associationsdata ([Pearl](https://ftp.cs.ucla.edu/pub/stat_ser/r475-cacm-reprint.pdf)). | Formulera orsakshypotes och alternativa förklaringar; säg när effekten inte kan identifieras. |
| Fysik | Kontrollera dimensioner, kapacitet och fysikaliska antaganden; dimensionsanalys kan identifiera sambandens form utan att alltid bestämma deras numeriska innehåll ([NIST](https://www.nist.gov/blogs/taking-measure/life-buckingham-pi)). | Ingen allmän agent ersätter konstruktionskompetens eller projektspecifik dimensionering. |
| Psykologi | Formulera prövbara hypoteser om kundbeteende, arbetsflöden och val. | Skilj observation från tolkning; använd etiska tester, inte diagnoser eller dold manipulation. |
| Historia | Pröva analogier genom kända, oklara och antagna förhållanden samt konkreta likheter och skillnader ([Studies in Intelligence](https://www.cia.gov/resources/csi/static/6-Analogical_Reasoning_in_Intelligence_Analysis.pdf)). | Datera jämförelsen, välj ett motfall och kontrollera mekanismen. |
| Filosofi | Klargöra mål, premisser och alternativa förklaringar; den bästa tillgängliga förklaringen är inte därmed bevisad sann ([Stanford Encyclopedia of Philosophy](https://plato.stanford.edu/entries/abduction/)). | Ange starkaste invändningen och vad som skulle ändra rekommendationen. |
| Beslutsteori | Fråga om mer information kan ändra beslutet; formell value-of-information-analys kräver specificerade alternativ, nytta och osäkerhetsfördelningar ([ISPOR:s metodrapport](https://pmc.ncbi.nlm.nih.gov/articles/PMC7373630/)). | Använd kvalitativt informationsvärde om data saknas; hitta inte på kr-värden. |
| Kvantfysik | Använd specialistkompetens vid ett verkligt kvanttekniskt problem; kvantberäkning bygger på kvantbitar och särskilda algoritmer och är inte bättre för alla slags problem ([IBM](https://www.ibm.com/think/topics/quantum-computing)). | Ingen kvantbackend är ansluten eller aktiverad här. Parallella LLM-agenter kallas inte kvantberäkning. |

### Agentstruktur

```text
Användarens mål och godkända omfattning
                    |
             Perplexity / Jarvis
                    |
      Uppgift, dataklass och kunskapslucka
                    |
          Minsta relevanta arbetsplan
                    |
      +-------------+-------------+
      |             |             |
  Research      Domänprövning   Motbevis
  vid behov      vid behov     vid behov
      +-------------+-------------+
                    |
       Källkontroll och beslutssyntes
                    |
      Isolerad kandidat: kod eller skill
                    |
       Tester och separat granskning
                    |
      Befintlig godkännandegrind
                    |
      Införande först efter rätt beslut
```

Detta är arbetsstrukturen som skillen beskriver. Den nya Python-planeraren returnerar bara planerade roller; den startar inte dessa agenter och får inte beskrivas som en redan inkopplad agentmotor.

## Rekommendation

Behåll en sammanhängande Jarvis-kärna och utöka den efter mätbara behov. Återanvänd befintligt GitHub, Supabase, Notion och projektets verktygsägarskap; skapa inte en andra kontrollpanel eller ett separat minnessystem för detta.

- **Behåll befintlig orkestrering:** LangGraph erbjuder redan byggstenar för tillstånd, varaktig exekvering, minne och mänsklig kontroll, men är inte en färdig researchintelligens ([LangGraph-dokumentationen](https://docs.langchain.com/oss/python/langgraph/overview)). Jag har inte installerat ett konkurrerande agentramverk.
- **Återanvänd och granska skills:** Anthropics publika skills-repo har olika licensförutsättningar för olika delar och är därför inte ett paket som bör kopieras okritiskt ([Anthropics skills-repo](https://github.com/anthropics/skills)). Jag har i stället förbättrat den befintliga Jarvis-skillen och inte installerat externa skills där nyttan och licensen är oklara.
- **Använd forum som upptäcktsspår:** DoWhys GitHub-diskussion innehåller API-förslag och olösta arkitekturfrågor, inte bevis på att alla förslag är införda ([DoWhy Discussion #429](https://github.com/py-why/dowhy/discussions/429)). Den kontrollerade dokumentationen beskriver däremot arbetsstegen model, identify, estimate och refute ([DoWhy v0.13](https://www.pywhy.org/dowhy/v0.13/user_guide/causal_tasks/estimating_causal_effects/index.html)).
- **Ingen blind självinstallation:** Välj nya plugins eller connectors först när en namngiven uppgift inte kan lösas tillräckligt väl med nuvarande verktyg. Kräv då dataklass, rättigheter, ägare, exakt version, licens, test, kostnadsunderlag och återställning.

Min arbetsregel blir: sök självmant när det behövs för det pågående uppdraget, pröva den starkaste invändningen och spara endast kontrollerade, återanvändbara förbättringar. Detta är inte ett tillstånd att kringgå lagar, licenser, behörigheter eller säkerhetsgrindar.

## Nästa steg

- **Kod till granskning:** Nästa externa åtgärd är att pusha den isolerade grenen och öppna en draft-PR i det privata `rickyraippalinna/jarvis-omega-v2`. Detta kräver ett specifikt godkännande enligt projektets regler; ingen merge, deployment eller workflow-trigger ingår.
- **Verklig kvalitetsmätning:** Därefter bör ett separat, låst jämförelsepaket byggas av representativa Jarvis-uppgifter, inklusive verkliga tidigare fel och syntetiska säkerhetsfall. Jämför enklare utförande med selektiv specialiststruktur och mät lösningsgrad, källkorrekthet, kritiska fel, väntetid och faktiskt rapporterad resursåtgång.
- **Kontrollpunkt:** Behåll en ny roll endast om den förbättrar det relevanta utfallet eller minskar resursåtgången utan kritiska regressioner. Vid utebliven nytta, oklara rättigheter eller nytt säkerhetsfel: återgå till baslinjen.
- **Återkommande research:** Ingen schemalagd bevakning har skapats. Ett sådant uppdrag behöver avgränsade ämnen, frekvens, destination, stoppregel och godkännande innan registrering.

Det finns ännu inget uppmätt kr-resultat eller belägg för en generell intelligensökning. Jag kan därför inte ge en trovärdig avkastningsprognos eller jämföra systemets intelligens med en viss person.

## Genomförd leverans

### Sparad skill

Den befintliga projektskillen `project:jarvis-ai-verktygskedja` är uppdaterad till version 1.2 med samma skill-ID och samma projektscope. Sparningen bekräftades och den sparade katalogen återlästes och jämfördes med kandidaten utan skillnader.

- **Researchslinga:** Kunskapslucka, källkedja, motbevis, minsta ändring, test, återställning och stoppregel.
- **Tvärvetenskaplig routing:** Matematik, fysik, psykologi, historia, filosofi, kausalitet och mjukvara används efter relevans.
- **Begränsad agentstruktur:** Små, separata bevisuppgifter och högst tre första specialistspår som arbetsstandard, inte en ny ekonomisk budget.
- **Förbättringsgrind:** Nytta, versionsbindning, separat utvärdering och rätt godkännande före införande.
- **Reparerade hänvisningar:** Aktuell browser-skill och tillgängliga modell-ID:n ersätter två föråldrade verktygshänvisningar.
- **Återställning:** Originalversion 1.1 finns bevarad i ett verifierat ZIP-arkiv. Den ersattes inte av en duplicerad personlig skill.

Skillen har validerats med `agentskills validate`. Beskrivningen har kontrollerats mot två relevanta begäranden och ett närliggande icke-fall: GitHub-lärande och tvärvetenskapligt beslut passar, medan putsanbud ska gå till BTF:s kalkylskill.

### Lokalt byggd kod

Arbetet ligger på grenen `feat/evidence-led-intelligence-20261031`, baserad på `main` vid commit `01dd84b`. Följande delar är byggda utan ändringar i befintlig supervisor, produktionsdatabas, provider-konfiguration, budgetgrindar eller workflows.

| Del | Vad den gör | Vad den inte gör |
|---|---|---|
| `planner.py` | Planerar 1–3 roller utifrån uttryckliga domänval. | Kör inte LLM-agenter eller automatiska ämnesklassificerare. |
| `github.py` | Gör begränsade, publika GitHub-läsningar via autentiserad `gh`, med metadata och exakt commit-SHA. | Hämtar eller kör inte repokod; granskar inte licensfilens innehåll. |
| `evidence.py` | Kontrollerar källkort, lästid, dubbletter, dataklass och deklarerat stöd. | Avgör inte sanningen och autentiserar inte källbedömaren. |
| `learning.py` | Kräver relevans, källor, tester, granskning, versionsbindning och återställning före `ready_for_review`. | Installerar, sparar, mergar eller driftsätter aldrig. |
| `scripts/jarvis_research.py` | Ger ett körbart JSON-gränssnitt för planering och explicit publik sökning. | Startar ingen scheduler, webbläsarfallback eller minnesinlärning. |

All ny runtimekod använder Python-standardbiblioteket. Befintliga beroenden och pytest installerades i en isolerad `.venv` för tester; inga globala produktionspaket eller nya modellleverantörer lades till.

### Verifiering

| Kontroll | Observerat resultat | Tolkning |
|---|---|---|
| Baslinje före ny kod | 69 tester och 100 deltester godkända. | Den befintliga testsamlingen fungerade i testmiljön. |
| Ny testsamling efter granskning | 132 tester godkända. | Täcker normalfall, fel, tomt svar, fallback, avbrott, känslig data, felaktiga svar, injektionsförsök och förslagsgrind. |
| Hela testsamlingen | 201 tester och 100 deltester godkända. | Ingen regression upptäcktes i denna testsamling. |
| Befintliga varningar | 13 deprecation-varningar från beroenden. | Kvarstår; inget påstående om varningsfri miljö. |
| Verkligt GitHub-lästest | Fem läsanrop, två kandidatkort och `search_completed`. | Adaptern fungerar mot den aktuella GitHub-åtkomsten; kandidaterna är fortfarande overifierad kod. |
| CLI-planering och hjälp | JSON-utdata; inga nätanrop för planering. | Lokalt gränssnitt testat. |
| Skillpaket och återställningsarkiv | Validerade och ZIP-integritet kontrollerad. | Paketen kan läsas; skillens beteende är inte därmed statistiskt effektutvärderat. |
| Produktionspåverkan | Ingen merge, deployment, ny automation eller produktionsskrivning. | Kodens status är TESTAT LOKALT, inte VERIFIERAT I DRIFT. |

Vid separat granskning rättades falska tidsvärden som annars kunde ersättas med aktuell tid, triviala namnvariationer som kunde se ut som en oberoende granskare och licensetiketter med olika skiftläge. Grinden tillåter nu att en dokumenterad baslinjebrist rättas, men blockerar kritiska fel i kandidaten och varje observerad PASS-till-FAIL-regression.

Tester av denna modul är inte samma sak som en blind, hållbar utvärdering av hela Jarvis förmåga. En sådan jämförelse återstår, och den nya grinden är ett förberedande rapportkontrakt, inte en ersättare för Approval Center.

### Underlag och täckning

Jag har läst relevanta personliga och projektspecifika kunskapssidor, den tidigare sessionen om GitHub-lärande, den befintliga verktygsskillens resurser samt aktuell `AGENTS.md`, supervisor, state, workflows och tester i Jarvis-repot. Jag har inte gått igenom alla historiska samtal eller alla projektfiler.

Det äldre lokala lärandepaket som beskrevs i tidigare samtal återfanns inte som åtkomlig källartefakt i de kontrollerade sökvägarna. Den nya koden bygger därför vidare på det verifierade befintliga repot; jag påstår inte att den äldre modulen har återanvänts, integrerats eller driftsatts.

Två researchspecialister och en kodspecialist användes i denna uppgift, följt av min egen käll- och kodgranskning. Specialistunderlagen har filtrerats: långtgående kvantmetaforer, obestyrkta generella effektlöften och krav som saknar relevanta data har inte förts in som driftregler.
