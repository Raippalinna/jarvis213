# Copilot Studio, Codex, GitHub och Lovable: säker integrationsväg

**Status: FÖRBEREDD, inte ansluten eller driftsatt.** Datum: 2026-11-19. Denna ändring omfattar dokumentation, två API-specifikationer och en offline-kontrakttest. Ingen workflow-variable, credential, produktionstjänst eller betalning har ändrats.

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
2. Välj rätt fil enligt produkten: **REST API-verktyget i Copilot Studio (preview)** kan importera `docs/integrations/copilot-studio-jarvis.openapi.json` (OpenAPI 3) och konverterar då till v2 internt; **äldre Power Platform Custom Connector** ska importera `docs/integrations/copilot-studio-jarvis.swagger2.json` (Swagger 2.0). Båda pekar på `https://api.github.com`. Verifiera importen och autentisering i just din miljö. Microsoft anger att REST API-funktionen är preview, inte avsedd för produktionsbruk, och kräver maker-behörighet samt Copilot Studio-licens.
3. Konfigurera en **säker anslutning** till GitHub med minsta möjliga rättigheter, avgränsad till repo:t `jarvis-omega-v2`. GitHubs dispatch-endpoint kräver `Contents: write` för fine-grained token, vilket är betydligt bredare än att bara få skicka ett event. Power Platform-v2-definitionen använder API key i headern `Authorization`: det hemliga anslutningsvärdet måste få formen `Bearer <token>`, men får **bara** anges i anslutningens skyddade credential-dialog, aldrig i chatt, prompt, repo eller export. Utvärdera helst en begränsad mellanhand med eget godkännande före produktionsdrift.
4. Verktyget `dispatchJarvisTask` ska bara köras efter **explicit mänsklig bekräftelse per uppdrag**, helst genom en tekniskt verkställd approval-grind i ett separat backend-/Power Automate-flöde. En prompt som säger 'be om godkännande' är inte en tillräcklig säkerhetsspärr. Fyll `event_type=jarvis-run`, `client_payload.task`, `client_payload.tier` (börja med `FREE`) och vid behov en UUID i `request_id`. Skicka inga hemligheter, persondata eller juridiska ärenden i payload.
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
| OpenAPI-filer v2 och v3 | Båda beskriver samma begränsade dispatch-anrop | Statiskt kontrollerade; import i Copilot EJ GJORD |
| Copilot-verktyg importerat | Syns i rätt agent med korrekt auth | EJ GJORT |
| GitHub-auth | Minsta nödvändiga repo-scope, secret skyddat | EJ GJORT |
| Extern dispatch | Explicit godkännande och spårbar run | SPÄRRAD |
| Lovable | Projekt/skills finns, faktiskt API-samband testat | EJ TESTAT |
| Kostnad | Inga nya köp; faktisk API/credit-förbrukning kräver kördata | EJ MÄTT |

**Rollback:** Stäng av/ta bort Copilot-verktyget eller dess anslutning, se till att `JARVIS_REPOSITORY_DISPATCH_ENABLED` är `false`, och stäng PR:en/återställ dokumentationsfilerna. Inga databasmigrationer eller workflows ändras här.

## Kontrakttester (utan liveanrop)

Kör från repo:ts rot:

```bash
python -m unittest discover -s tests -p 'test_copilot_openapi_contract.py'
```

Testet kontrollerar API-version, exakt dispatch-endpoint, payload, behörighetsdeklaration, att inga GitHub-nycklar är inbakade och att workflow-gaten fortfarande finns. Detta testar **inte** att Copilot accepterar importen, att autentiseringen fungerar, att en användare verkligen bekräftar uppdrag eller att GitHub Actions körs. Kräv separata kvitton för dessa påståenden.

**Säkerhetsbeslut:** Ingen produktionsaktivering med enbart promptbaserat godkännande och en direkt `Contents: write`-token. Lägg först till tekniskt verkställd approval, helst en begränsande mellanhand som endast exponerar detta dispatch-event, och använd en dedikerad credential. Verifiera också DLP-policy och Copilot Studio-kostnad för miljön.

## Källor

- [OpenAI: Using Codex with your ChatGPT plan](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
- [Microsoft: Add tools to custom agents](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-tools-custom-agent)
- [Microsoft: Extend agent with REST API (preview)](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agent-extend-action-rest-api)
- [Microsoft: Custom Connector FAQ (Swagger 2.0)](https://learn.microsoft.com/en-us/connectors/custom-connectors/faq)
- [GitHub: REST repository dispatch](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event)
