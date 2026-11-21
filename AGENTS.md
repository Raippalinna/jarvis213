# AGENTS.md — regler för kodagenter i JARVIS Ω∞ OS v2

Den här filen läses av Codex (cloud och CLI), Cursor och andra kodagenter som arbetar i repot.
Orkestrator och beslutsägare är Perplexity Computer ("Jarvis") på uppdrag av Ricky Raippalinna.
Reglerna är en delmängd av Jarvis projektinstruktioner; vid konflikt gäller Jarvis och Ricky.

## Roller

- **GitHub** är versionsstyrd kod. **Supabase** är produktionsdata. **Notion** är kontrollrum.
  Neon är inte produktionsdatabas, Asana är inte aktivt uppgiftssystem.
- Du levererar en branch och en PR mot `main`. Du mergar aldrig till `main` själv.
- Jarvis granskar diffen, kör tester och rapporterar status till Ricky.

## Absoluta gränser

1. Rör inte kill switch, `DRY_RUN`, `system_config.autonomy_enabled` eller godkännandelogik
   (Approval Center) för att komma runt en spärr. Godkännande är deterministisk kod, inte en LLM.
2. Inga hemligheter i kod, tester, loggar, commit-meddelanden eller PR-text. Använd `.env.example`
   och GitHub Secrets. Läs aldrig upp innehåll i `.env`.
3. Lägg inte till workflows som triggas på `push`/`pull_request` och kostar pengar (LLM-anrop,
   externa API:er). Befintliga workflows körs via `schedule`, `workflow_dispatch` eller
   `repository_dispatch`; bevara det.
4. Inga externa utskick (Slack, e-post, Notion-skrivningar mot verkliga sidor) från tester.
   Tester ska vara tysta utan nycklar, precis som `jarvis_cloud.py` är.
5. Ändra inte modellleverantör, budgettak eller tier-tabellen i `src/jarvis/routing/providers.yaml`
   utan att uppdraget uttryckligen begär det.

## Arbetssätt

- Minsta sammanhängande förbättring. Bevara original och beskriv återställning i PR-texten.
- Skriv på svenska i dokumentation, commit-meddelanden och PR-text; kod och identifierare på engelska.
- Kör `python -m pytest tests -q` före PR. Om beroenden saknas: `pip install -r requirements.txt`.
- Testa lyckad körning, fel, tomt svar, fallback och avbrutet uppdrag när du ändrar körvägar.
- Skilj i PR-texten mellan FÖRBERETT, TESTAT LOKALT, SPARAT, DRIFTSATT och VERIFIERAT I DRIFT.
  En grön testkörning är inte driftsättning.
- Hitta inte på körresultat, siffror eller källor. Skriv "ej verifierat" när du inte kört något.

## Repo-karta

- `jarvis_cloud.py` — inträdespunkt för GitHub Actions-körningen.
- `src/jarvis/` — LangGraph-supervisor, agenter, routing (`routing/providers.yaml`), minne.
- `supabase/` — migrationer och SQL; ändringar här kräver Rickys godkännande före körning.
- `scripts/` — engångs- och kontrollskript (t.ex. `jarvis_connection_check.py`).
- `tests/` — pytest; håll dem nyckelfria.
- `docs/` — daterade beslut och bevis (`docs/evidence/`).
- `wiki/` — projektkunskap som speglas till Perplexity-projektet Jarvis.

## PR-mall

```
Mål:
Ändrat:
Testat (kommando + resultat):
Ej verifierat / återstår:
Återställning:
Status: FÖRBERETT | TESTAT LOKALT | SAVED/PR
```
