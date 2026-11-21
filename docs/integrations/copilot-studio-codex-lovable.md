# Copilot Studio, Codex, GitHub och Lovable: säker integrationsväg

**Status: FÖRBEREDD, inte ansluten eller driftsatt.** Uppdaterad: 2026-11-19. Denna ändring omfattar enbart dokumentation och en OpenAPI-kandidat. Ingen workflow-variable, credential, produktionstjänst eller betalning har ändrats.

## Verifierad nulägesbild

- `rickyraippalinna/jarvis-omega-v2` har redan en `repository_dispatch`-trigger med eventtypen `jarvis-run` i `.github/workflows/jarvis-cloud.yml`.
- Workflow-jobbet körs **inte** för externa repository_dispatch-anrop om inte repository-variabeln `JARVIS_REPOSITORY_DISPATCH_ENABLED` uttryckligen är `true`. Ändra inte spärren på grund av denna PR.
- `scripts/resolve_jarvis_inputs.py` validerar `task` (1–8000 tecken), `tier` (FREE/LOW/MED/HIGH) och valfritt `request_id` (UUID). `origin` är bara en obevisad avsändaruppgift, inte autentisering.
- ChatGPT/GitHub har åtkomst till det privata repo:t. Lovable-konton och arbetsytor är separata anslutningar, inte automatiskt gemensamma behörigheter.
- I Lovable finns redan projektet **Adaptive Skills Orchestra** och arbetsytans `ricky-jarvis-control-plane`- och `ricky-fleet-ops`-skills. Skapa inte dubbletter. Ingen verifierad Copilot-koppling till detta projekt.
- Microsoft Copilot Studio-agentens liveinställningar kunde inte läsas i vanlig ChatGPT-chatt. Ingen installation i Copilot påstås.

## Avsedd arkitektur

```text
Copilot Studio-agent (mänsklig instruktion och bekräftelse)
   -> REST API-verktyg / säker custom connector med GitHub-autentisering
   -> GitHub POST /repos/rickyraippalinna/jarvis-omega-v2/dispatches
   -> event_type "jarvis-run", client_payload { task, tier, request_id? }
   -> repository_dispatch-gate (AV som standard)
   -> JARVIS workflow + avgränsade artefakter + revisionslogg
```

Detta skapar **inte** en delad inloggning mellan ChatGPT, GitHub, Lovable och Microsoft. Varje system kräver egen behörighetskontroll. I detta steg används inte Lovable som relay eller hemlighetslager.

## Importera först när autentisering kan verifieras

1. I [Copilot Studio](https://copilotstudio.microsoft.com/): öppna rätt agent och gå till **Tools / Add a tool**. Välj REST API-verktyg om funktionen finns i din miljö, annars en **custom connector** med motsvarande API-definition.
2. **Importera i första hand `docs/integrations/copilot-studio-jarvis.swagger2.json` (Swagger/OpenAPI 2.0)**. Microsofts REST API-verktyg arbetar med v2 och kan försöka översätta v3 automatiskt, men den separata v2-filen undviker onödig konvertering. Den tidigare `copilot-studio-jarvis.openapi.json` (v3.0.3) behålls som referens. API-basen är `https://api.github.com`. Inget importtest har utförts i din Microsoft-miljö.
3. Konfigurera **säker användar-/tjänsteanslutning** till GitHub med minsta möjliga rättigheter, avgränsad till repo:t `jarvis-omega-v2`. För endpointen `Create a repository dispatch event` krävs enligt GitHubs dokumentation `Contents: write` för fine-grained token. Swagger 2.0-importen använder API-nyckel i HTTP-headern `Authorization`: anslutningens skyddade värde måste vara `Bearer <token>`, inte endast tokensträngen. Ange detta **enbart i Copilot Studios skyddade anslutningsgränssnitt** (aldrig i chat, källkod, dokument eller dialogprompt), och testa den valda autentiseringsmetoden separat. Föredra en hanterad, roterbar anslutning och granska om behörigheten är acceptabel före aktivering.
4. **Tvinga bekräftelse i Copilot Studio-inställningarna** för `dispatchJarvisTask`: sätt **Ask the end user before running = Yes**, och **Allow agent to decide dynamically when to use the tool = No** så att verktyget bara kallas från en uttrycklig topic/action. Detta är faktiska verktygsinställningar enligt Microsofts dokumentation, inte enbart text i en prompt. Kontrollera att en topic kräver bekräftelse per uppdrag och att avslag stoppar anropet. Fyll `event_type=jarvis-run`, `client_payload.task`, `client_payload.tier` (börja med `FREE`) och vid behov en slumpgenererad UUID i `request_id`. Skicka inga hemligheter, persondata eller juridiska ärenden i payload.
5. Håll `JARVIS_REPOSITORY_DISPATCH_ENABLED` **inaktiv** tills en separat ändringsgranskning har godkänt autentisering, säkerhetsmodell, kostnadsgränser, innehållsfilter och tester.
6. När en särskilt godkänd provkörning görs: kontrollera först anslutningens inloggning och GitHub-API-svar med syntetiskt innehåll. HTTP `204` betyder bara accepterat event, **inte** att en körning startats eller slutförts. Kontrollera därefter Github Actions run ID, jobbstatus, resultat-artifact och loggar. Avsaknad av run eller 'skipped' är inte driftgodkännande.
7. Efter säkerhetsgranskning och särskilt godkännande för produktion kan aktivering av dispatch-gaten behandlas som en **separat åtgärd** med omedelbar rollback genom att sätta variabeln till `false`.

## Codex med ChatGPT-plan

- Gå till [Codex](https://chatgpt.com/codex), Codex-CLI eller IDE-tillägget och logga in med **samma ChatGPT-konto**. Dessa klienter kan använda planens Codex-behörighet, med aktuella planbegränsningar. Det skapar **ingen** delad API-kvot för Microsoft eller Lovable.
- Välj detta GitHub-repo som kodbas och låt Codex läsa repo:ts redan befintliga `AGENTS.md`. Gör ändringar i egen gren och PR, inte direkt på `main`.
- Separata Codex-körningar i molnet behöver sin egen aktiverade miljö och GitHub-behörighet. Denna PR ansluter inte Codex Cloud automatiskt.

## Lovable och dataisolering

- Lovables **Adaptive Skills Orchestra** är ett befintligt app-projekt, men dess koppling till GitHub-dispatch eller Copilot är **inte verifierad**. Behåll nuvarande projekt som UI-/skillspår utan att ge det GitHub-uppgifter eller produktionsnycklar i klartext.
- `jarvis-core` är befintlig MCP-/integrationskod; blanda inte dess Supabase-miljö och `jarvis-omega-v2` utan dokumenterad datamodell och tenant-test.
- Skilj strikt Rickys projekt från andra personers rättsärenden, ekonomiska uppgifter och NEO-/Perplexity-arkiv. Ingen generell datadelning mellan privata arbetsytor.

## Acceptanskriterier och verifiering

| Kontroll | Krav | Status efter denna PR |
| --- | --- | --- |
| GitHub-event och payload | Matchar befintlig workflow och input-validering | Granskad mot källfiler |
| OpenAPI-fil | Kan parsas och beskriver ett enda begränsat dispatch-anrop | Granska JSON lokalt/i CI |
| Copilot-verktyg importerat | Syns i rätt agent med korrekt auth | EJ GJORT |
| GitHub-auth | Minsta nödvändiga repo-scope, secret skyddat | EJ GJORT |
| Extern dispatch | Explicit godkännande och spårbar run | SPÄRRAD |
| Lovable | Projekt/skills finns, faktiskt API-samband testat | EJ TESTAT |
| Kostnad | Inga nya köp; faktisk API/credit-förbrukning kräver kördata | EJ MÄTT |

**Rollback:** Stäng av/ta bort Copilot-verktyget eller dess anslutning, se till att `JARVIS_REPOSITORY_DISPATCH_ENABLED` är `false`, och stäng PR:en/återställ dokumentationsfilerna. Inga databasmigrationer eller workflows ändras här.

## Källor

- [OpenAI: Using Codex with your ChatGPT plan](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
- [Microsoft: Add tools to custom agents (bekräftelse och dynamisk användning)](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-tools-custom-agent)
- [Microsoft: Extend agent with REST API (preview), Swagger v2 och anslutning](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-rest-api)
- [GitHub: REST repository dispatch](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event)
