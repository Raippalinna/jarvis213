# Evidence-led intelligence: avgränsad lokal runtime

Denna utökning ger Jarvis en körbar, behovsstyrd researchväg och deterministiska
granskningskontrakt. Den kopplar inte in nya agenter i befintlig supervisor och
ändrar inte databas, modeller, leverantörer, budgetgrindar, workflows eller
godkännandelogik. Ett kandidatkort är inte en lärdom, säkerhetsgranskad kod eller
ett verifierat faktum.

## Körning och status

All ny runtime använder Python-standardbiblioteket. Kör från reporoten:

```sh
python scripts/jarvis_research.py --help
python -m scripts.jarvis_research --task "Granska ett publikt Python-verktyg" --domain mjukvara
```

Det andra kommandot är en lokal planeringsfixture. Det gör inga nätanrop och
skriver inga filer. Även hjälptext returneras som ett JSON-objekt på stdout.
Argumentfel återger inte rå argument eller parserfel.

En verklig GitHub-sökning måste uttryckligen begäras:

```sh
python scripts/jarvis_research.py \
  --task "Bedöm offentliga referensprojekt för schemavalidering" \
  --domain mjukvara \
  --search \
  --public-query "python schema validation" \
  --sensitivity public \
  --public-query-reviewed
```

Flaggan `--public-query-reviewed` är ett krav på att användaren eller
orkestratorn redan har granskat och sanerat frågan, inte en automatisk
sekretessklassificering. Skicka aldrig kundnamn, hemligheter, personuppgifter,
privat kod eller interna söktermer som publik fråga. Den lokala uppgiften skickas
inte till GitHub och återges inte i resultatet. Kommandoargument kan dock synas
i operativsystemets processlista och shellhistorik; ange därför inga hemligheter
ens som lokal uppgift.

Utdata har följande tillstånd:

- **prepared**: lokal plan, inga specialistroller körda.
- **search_completed**: samtliga valda kandidatkort har publik metadata och exakt SHA.
- **no_results**: lyckad sökning som faktiskt returnerade en tom lista.
- **partial**: sökningen lyckades men minst en kandidat, granskning eller budget saknas.
- **unavailable**: GitHub/gh eller det första söksvaret kunde inte användas.
- **blocked**: uppgift, policy, publik granskning eller budgetkrav saknas.
- **cancelled**: uttrycklig avbrytning, cancellation-hook eller tangentbordsavbrott.

Exitkod är 0 för prepared/search_completed/no_results, 1 för
blocked/unavailable/partial och 130 för cancelled. Partial/unavailable ger bara
en ärlig rekommendation `manual_web`, aldrig påhittade webbsökresultat.
Ingen fallback-webbläsare startas automatiskt.

## Planerade specialistroller och begränsning

`plan_research` väljer endast uttryckligen angivna domäner: matematik, fysik,
psykologi, historia, filosofi och mjukvara, med engelska alias. En vanlig uppgift
får högst en roll. `--complexity multi_domain` kan planera högst tre relevanta
roller i angiven prioritetsordning; övriga läggs i `deferred_domains`.
Utan domän används en generell evidensresearcher, inte påhittad specialistkompetens.
Varje roll har status `PLANERAT`; `agents_executed` och `models_called` är noll.

Budgeten anges i faktiska tak: högst tre kandidat-repon, sju gh-anrop och tio
sekunders subprocess-timeout per anrop. En full körning kan därför vänta upp
till cirka 70 sekunder i subprocesser. Färre anrop kan begäras, med partial som
ärlig följd om ett kandidatkort inte hinner färdigställas. Ingen penningkostnad
uppskattas och ingen abonnemangs- eller API-budget ändras.

## GitHub-adapterns säkerhetsgräns

`search_public_repositories` använder endast redan autentiserad `gh search repos`
och `gh api --method GET`. Subprocesser använder argumentlistor, `shell=False`
och timeout. Både värd och API-metod är fasta. Publik sökning är ett fast filter,
och såväl sökträff som repositorymetadata måste uttryckligen ange publikt repo.
Repositorynamn matchas mot en strikt regex innan en API-sökväg byggs.

Endast metadata, licens-ID, arkivstatus och senast observerad exakt commit-SHA
hämtas. Licensen kommer från repositorymetadata vid läsning, inte från en
granskad licensfil på SHA:n. Kandidaten bär därför `license_reviewed: false`,
`code_read: false`, `safe_to_execute: null` och evidensstatus `unverified`.
Ett arkiverat repo eller okänd licens kan visas, men är aldrig automatiskt
rekommenderat för användning. Repositoryns publika status och HEAD kan ändras
efter läsningen; observation är inte ett bestående åtkomst- eller säkerhetslöfte.

Källbeskrivningar och commitsmeddelanden kopieras inte in som instruktioner.
Adaptern klonar inte, läser inte repositorykod, kör inte hämtad kod och följer
inga källstyrda URL:er eller kommandon. Rå stderr, felmeddelanden, tokens,
miljövariabler och råa sökfrågor loggas inte. Spårning innehåller bara tillåtna
steg, kandidatindex och sanerade framgångs-/felkoder.

Sökfrågan tillåter enkla sökord, blanksteg, punkt, understreck och bindestreck,
men inte URL:er, shellsyntax, radbrytningar eller GitHub-filter som kan ändra
synlighetskravet. Cancellation-hooken kontrolleras före varje anrop.

## Evidenskontrakt och ursprung

Varje kort kräver `url`, `fetched_at`, `kind`, `publisher`, `origin`,
`actual_read`, `claim`, `status` och `sensitivity`. Tidsstämpeln ska ha tidszon.
Framtida eller för gamla observationer, saknade fält, feltext, oläst material
och känsligt underlag stänger grinden. Standardgränsen är 30 dagar sedan
hämtning; det är inte en bedömning av källans publiceringsdatum eller aktualitet.

`assess_evidence` returnerar endast `eligible_for_review` eller
`insufficient_evidence`, aldrig ett sanningsvärde eller en sanningsscore.
`supported` är en tidigare mänsklig eller agentbaserad källbedömning som
anroparen måste ha gjort. Modulen kontrollerar struktur och policy men kan inte
bevisa att innehållet är sant, faktiskt läst eller korrekt tillskrivet.
`truth_verified_by_module` är aldrig true.

Två skilda, faktiskt lästa och upstream-bedömda stödjande ursprung krävs.
Forum och modellröster kan inte själva uppfylla detta. Modellöverensstämmelse
är inte oberoende källstöd. Samma normaliserade ursprung eller URL räknas inte
två gånger, även med olika publikationstitlar eller URL-fragment. Anroparen
måste märka syndikerade texter med samma ursprung; automatisk upptäckt av
felaktiga eller bedrägliga ursprungsetiketter ingår inte.

## Förslag, skills och lärandegrind

`review_proposal(proposal)` är en ren, deterministisk funktion. Den returnerar
bara `ready_for_review` eller `blocked` med skäl. Den installerar inte skills,
sparar inte agentminne och kan inte publicera, merge:a eller driftsätta.
Ett process- eller skillförslag kan använda samma kontrakt, men en skill som
innehåller kod ska ange `changes_code: true`.

Ett förslag måste innehålla:

- **Syfte**: `task`, `relevance`, `author`, `sensitivity: public` och explicit `cancelled: false`.
- **Kandidatbindning**: `candidate_hash`, en SHA-256-digest med 64 hextecken.
- **Källstöd**: `evidence` som klarar ovanstående strukturella policy.
- **Kodkälla**: vid kodändring krävs `source_version`, exakt 40-teckens commit-SHA,
  samt `source_url` till `https://github.com/OWNER/REPO/tree/SHA`.
- **Licensreview**: vid kodändring krävs `license_review` med `reviewed: true`,
  `reviewer`, konkret `license`, samma `source_version` och `compatible: true`.
  NOASSERTION/UNKNOWN/NONE är inte en licensgranskning.
- **Oberoende review**: `independent_review` med annan `reviewer` än `author`,
  `verdict: approved` och samma `candidate_hash`.
- **Återställning**: konkret, icke-tom `rollback`.
- **Utvärdering**: `evaluation` med `held_out: true`, explicit
  `training_case_ids` samt `baseline` och `candidate`.

Varje utvärderingsrapport innehåller `hash` och `cases`, där varje fall har
`id`, `category` och `outcome: PASS|FAIL`. Kandidatrapportens hash måste matcha
kandidaten, och baseline måste ha egen SHA-256-bindning. Båda rapporterna måste
använda samma held-out-fall och kategorier, skilda från träningsfallen.
Kategorierna `success`, `safety`, `error`, `empty`, `fallback`, `cancel` och
`sensitive` måste finnas i båda rapporterna och alla ha PASS i kandidaten.
Ett dokumenterat baslinjefel får rättas, men en PASS till FAIL-försämring
även i andra kategorier blockerar. Identiska PASS-resultat ger inte bevis för
förbättrad kvalitet; resursvinst eller annan nytta måste mätas separat.

Detta är ett rapportkontrakt, inte en testmotor: testerna och den oberoende
granskningen måste köras separat. Modulen autentiserar inte granskaridentiteter,
beräknar inte hash över en extern kandidat, bevisar inte att testfall är hemliga
och hittar inte semantiskt likvärdiga train-/held-out-fall med olika ID.
`ready_for_review` innebär därför inte ett användargodkännande eller promotion.

## Verifiering, non-goals och återställning

Kör lokala, nyckelfria tester:

```sh
python -m pytest tests/test_intelligence.py -q
python -m pytest tests -q
```

Testerna mockar alla subprocessanrop till gh, inklusive CLI-fixturen. De täcker
lyckad körning, tomt svar, felaktiga svar, saknad gh, fel/timeout, manuell fallback,
sekretess, avbrott, kommandoinjektion, framtida/gammal/dubblerad evidens samt
saknad baseline, train/held-out-överlapp och regression.

Avsiktliga non-goals är produktionsintegration, bakgrundsautomation,
LLM-agentkörning, byte eller tillägg av modeller, autonom skillinstallation,
obeställd datainsamling, perfekt prompt-injection-skydd och självlärande
persistent minne. Den befintliga produktionsgrinden är oförändrad. Om denna
modul senare integreras måste orkestratorn fortfarande läsa aktuell
autonomiflagga, respektera kill switch/DRY_RUN och inhämta rätt godkännanden.

Återställning består av att ta bort de nya filerna under
`src/jarvis/intelligence/`, `scripts/jarvis_research.py`,
`tests/test_intelligence.py` och detta dokument. Inga befintliga körvägar eller
produktionsresurser behöver återställas. Sparad kod och lokala tester är inte
DRIFTSATT eller VERIFIERAT I DRIFT.
