# Intelligence-utökning: verifiering 2026-10-31

Status: TESTAT LOKALT. Ingen produktionsintegration, merge eller bakgrundsautomation ingår.

## Reproducerbara tester

```sh
.venv/bin/python -m pytest tests/test_intelligence.py -q
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/jarvis_research.py --help
.venv/bin/python scripts/jarvis_research.py --task "Kontrollera ett arbetsflöde" --domain mjukvara
```

Baslinjen före utökningen gav 69 godkända tester och 100 godkända deltester.
Slutresultatet gav 132 nya godkända tester, totalt 201 tester och 100 deltester.
Båda körningarna hade 13 deprecation-varningar från befintliga beroenden.

En separat verklig, publik GitHub-sökning med frasen `agent evaluation`, högst två
källor och fem anrop gav `search_completed`, två kandidatkort och exakt fem gh-anrop.
Observationen gjordes cirka 12:10 UTC. Ingen repokod hämtades, installerades eller kördes.
Kandidatmetadata märktes `unverified`, `license_reviewed: false` och `code_read: false`.

## Föräldraagentens separata granskning

- Tidsvalideringen avvisar även falsy värden i stället för att tolka dem som aktuell tid.
- Granskarens namn normaliseras innan jämförelse med kandidatförfattaren.
- Okänd licens avvisas även vid omgivande blanksteg eller andra skiftlägen.
- En dokumenterad baslinjebrist kan rättas; kandidaten måste klara alla kritiska fall.
- PASS till FAIL, saknade jämförelsefall och överlapp med utvecklingsfall blockerar.
- Nya tester och koden har lästs separat från kodagentens sammanfattning.

## Begränsningar

Detta är lokala beteende- och regressionstester, inte en blind kvalitetsutvärdering
av hela Jarvis. Testerna medför ingen allmän säkerhetsgaranti och mäter ingen kr-effekt.
Förslagsgrinden autentiserar inte testresultat, källbedömning eller granskare.

Den nya koden ändrar inte supervisor, Approval Center, Supabase, workflows,
modellleverantörer eller abonnemang. Den sparade projektskillen är en separat
instruktionsändring, inte bevis för att Python-koden finns i produktion.
