# Jarvis: integrationskontroll och samordnat ändringspaket

Datum: 2026-09-25. Status: lokalt testat, avsett för befintlig utvecklingsgren i PR #2, inte produktionssatt.

## Slutsats

GitHub → modell → Notion har verifierats för ett befintligt test, men hela Comet Assistant → Edge Function → GitHub → Notion är fortfarande inte verifierad. Testets egen formulering ”Comet-vägen fungerar” är genererad text och får inte användas som bevis för den del av kedjan som testet hoppade över. [Testkörning](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/36176787846) · [Kontrollrum](https://app.notion.com/p/3ca66d43c107813b90f3daf5b5a42333).

## Ändringar i detta paket

- Synkroniserar den befintliga förbättringsgrenen med main vid `f0077eb1579278f15afb7fa341c7c3de2aaf1b1b`. Löser add/add-konflikten i `test_huggingface_preflight.py` genom att behålla båda testernas skilda skydd: manuellt HF-identitetstest och isolerat anslutningsflöde.
- Förbereder en enradig CORS-rättning i `jarvis-comet`: lägger till `x-jarvis-key` i redan befintliga `Access-Control-Allow-Headers`. Ändrar inte autentiseringsnyckel, tillåtna origins, JWT-inställning, destination eller uppdragskörning.
- Lägger till ett lokalt OPTIONS/preflight-test utan nätverk och behåller negativa autentiserings-, kill-switch- och dispatchtester. Det immutabla v6-originalet behålls; testet tillåter endast det isolerade anslutningsblocket och den uttryckliga headerändringen.
- Kör Comet-testsviten även i befintlig offline-CI. Inga produktionshemligheter används av den testkörningen.

## Lokala resultat

| Kontroll | Resultat |
|---|---|
| Python unittest discovery | 199 tester, OK |
| PGlite approval-tester | 22 tester, 22 godkända |
| Comet-fixturer | 46 testfall, 0 nätverksanrop |
| Perplexity-konfigurationsfiler | 4 fält godkända offline; inte bevis för kontoinställningar |
| `git diff --check` | Inga whitespace-fel |

Kommandon, körda från repo-roten:

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -v
node tests/test_connection_check.mjs
npm ci --prefix tests/sql --no-audit --no-fund
npm test --prefix tests/sql
python scripts/check_perplexity_config.py
git diff --check
```

## Verifierat i befintlig drift

- GitHub-run `36176787846` är `completed/success`, skapad 18:58:25 UTC. Den var redan startad i föregående session och kördes inte om här. [GitHub](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/36176787846).
- Notion har den exakta testuppgiften från samma tid samt svaret ”Kopplingstest bekräftat: Comet-vägen fungerar.” Lästs via Comet eftersom den stora connectorhämtningen inte innehöll sista posten; Notion-sökningen hittade också posten. Posten rapporterar kvalitetsvärdet 0,15, vilket inte ska omtolkas som ett kvalitetsgodkännande. [Notion](https://app.notion.com/p/3ca66d43c107813b90f3daf5b5a42333).
- Jarvis-projektets instruktioner återlästes genom Project CLI. De skiljer ansluten tjänst, verifierat flöde och driftsatt kod; instruktionerna ändrades inte. [Jarvis-projektet](https://www.perplexity.ai/projects/jarvis-HzuJXAVLQ2K9Uh2zEcpMOQ).

## Connectorstatus och begränsningar

Läsning via connectorverktyg 2026-09-25; nedan är observerad kontostatus, inte bevis för automatiserade flöden.

| Grupp | Observation |
|---|---|
| 20 kartlagda tjänster | 17 CONNECTED; Slack, Stytch och LegalZoom DISCONNECTED |
| Exkluderade roller | Asana fryst, Spotify privat, LegalZoom inte för svenska bolags-/avtalsflöden; inget aktiverat |
| Återauktorisering | Slack, Stytch och Dropbox MCP kräver användarens OAuth-godkännande; nya flöden öppnade |
| Dropbox | Legacy CONNECTED; MCP OUTDATED vid kontroll, återauktorisering begärd |
| Supabase | JARVIS Prime ACTIVE_HEALTHY; `autonomy_enabled` = `"true"`; `jarvis-comet` v7 ACTIVE |
| Outlook | Mappläsning lyckades |
| HubSpot | Portal 149094503, `onboarded=false`, mål `NOT_STARTED`; innebär inte att CRM är tomt |
| Övriga kontrollerade kandidater | Linear, Vercel, Hugging Face, Stripe, Whimsical, Amplitude, PostHog, Google Drive, Gmail/Calendar och Finance CONNECTED; inga nya roller eller skrivflöden tilldelade |

Se alla HubSpot-onboardinguppgifter i [startguiden](https://app-eu1.hubspot.com/user-guide/149094503). Inget mål har satts, inga CRM-poster har ändrats och inget abonnemang har uppgraderats.

## Kvarstående produktionsgrindar

- Godkänn CORS-rättningen specifikt innan ny Edge Function-version driftsätts. Behåll samma funktion, projekt, nycklar och `verify_jwt=false`.
- Ordna säker tillgång till endpointautentisering utan nyckel i chatt, URL eller logg. Kör därefter det isolerade `verify_connection`-flödet från rätt browserklient och matcha check-ID till GitHub-resultatet.
- Full normal uppdragsväg behöver ett separat avgränsat test med exakt task, mål, kostnadsram och återläsning. Ett anslutningstest utan modell får inte beskrivas som full modell-/minnesintegration.
- Slå inte samman hela PR #2 enbart för CORS-rättningen. PR:n innehåller även godkännandelagring, minnesisolering och andra ändringar med egna releasegrindar. Läs `docs/approval-atomic-20260922.md` och `docs/completion-api-safety-20260920.md`.
- Daterad kodgranskning: den normala Edge Function-vägen v7 kontrollerar inte själv kill switch före dispatch; kontrollen finns i det isolerade testblocket. Att flaggan är true är inte bevis för att alla körvägar kontrollerar den.
- Slack-connectorns frånkoppling gäller Computer-autentisering. GitHub:s separata webhook/bot kan inte dömas ut utan eget leveransprov.
- HubSpot-onboarding behöver ett konkret verksamhetsmål innan `SET_GOAL`; ”kör allt” väljer inte CRM-process eller dataimport.

## Transportfel

Gap: `github_mcp_direct` CONNECTED men Actions-artifactdownload gav HTTP 401 och run-jobs-vyn HTTP 404; run-metadata och git fungerade. Comet-fallback visade GitHub utloggat, så inga inloggningsförsök eller hämtningar gjordes där; Notion-readback användes som alternativt leveransbevis.

`pplx skill list --scope project` kunde inte köras eftersom `PPLX_SKILL_BASE_URL` saknades. Project-get visade projektets befintliga `jarvis-konfigurationskontroll`; ingen fullständig skillbiblioteksinventering påstås.

## Återställning

Detta ändrar inte main eller Supabase-produktion. Innan produktionsgodkännande: lämna PR:n osammanslagen. Efter ett eventuellt separat godkänt Edge-deploy kan headern återställas till `Content-Type, Authorization` med samma övriga v7-kod; det återinför dock browserpreflight-felet.
