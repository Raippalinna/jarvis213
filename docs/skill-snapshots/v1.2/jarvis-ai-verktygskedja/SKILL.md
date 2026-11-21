---
name: jarvis-ai-verktygskedja
description: "Jarvis AI-orkestrering, specialistagenter och behovsstyrd research: välj kod, modell, Comet, Codex, Cursor, Lovable eller skill. Använd vid verktygskoppling, tvärvetenskapliga beslut och testbar självförbättring. Inte för connector-hälsa, tjänsteägarskap, vanlig faktasökning eller BTF-kalkyl."
metadata:
  author: ricky-raippalinna
  version: '1.2'
  perplexity:
    connectors:
      - id: github_mcp_direct
        reason: GitHub är bryggan mellan Jarvis, Codex cloud och Cursor; utan den kan inte PR:ar granskas eller AGENTS.md hållas i synk.
      - id: slack_direct
        reason: Kandidatkanal för Cursor Background Agents och Codex-notiser.
      - id: supabase
        reason: Läs system_config.autonomy_enabled före autonom sidoeffekt.
---

# Jarvis AI-verktygskedja

Perplexity Computer är orkestratorn. ChatGPT, Codex, Cursor och Lovable är utförandearmar som möts i
GitHub (`rickyraippalinna/jarvis-omega-v2` för automation, Lovable-repona för apparna); `AGENTS.md` i
varje repo bär Jarvis-reglerna in i dem.
Lägg inte till en ny arm om en befintlig redan täcker behovet; fler råa verktyg sänker träffsäkerheten.

## Välj minsta tillräckliga väg

Läs `references/kostnadsmedveten-orkestrering.md` före val som påverkar modellnivå,
abonnemangsåterbruk, automatisk synk eller förslag till självförbättring.
Läs `references/verktygsval.md` när uppgiften ska fördelas till en konkret AI-arm.
Utgå inte från att fler modeller är bättre; använd testbara kvalitetskrav och relevanta källor.

## Research och specialistagenter

Läs `references/research-och-forbattring.md` när användaren vill utveckla Jarvis,
lära från GitHub/forum, utvärdera plugins eller arbeta med en researchagent.
Sök självmant inom den aktuella uppgiften när en namngiven kunskapslucka påverkar resultatet.
Detta aktiverar inte en bakgrundsbevakning eller obegränsad installation.

Läs `references/tvarvetenskap.md` när flera kunskapsfält kan ändra ett beslut.
Välj bara relevanta specialister och ge dem separata bevisuppgifter; slå inte rutinmässigt på alla.
Skilj förbättrade verktyg, arbetssätt och minne från ändrade modellvikter eller bevisad intelligens.

## Arbetsordning vid kodärende till Codex eller Cursor

1. Läs `AGENTS.md` och aktuell branch i repot med `gh`/`git` (credential `github`); bekräfta att inga push-triggade workflows startar kostnad.
2. Läs `system_config.autonomy_enabled` i Jarvis-Supabase; false eller okänt = ingen autonom sidoeffekt, bara förberedelse.
3. Formulera uppdraget med mål, filer, testkommando och förbjudna ändringar (hemligheter, kill switch, DRY_RUN, workflows med kostnad). Skicka via Codex cloud-UI i lokal webbläsare eller som GPT-subagent i sandboxen.
4. Hämta PR:en, kör `git diff` och testerna själv i sandboxen; leta hemligheter i diffen.
5. Rapportera status: FÖRBERETT, TESTAT LOKALT, SPARAT (PR öppen), DRIFTSATT (merge, kräver godkännande), VERIFIERAT I DRIFT (körning observerad).

Klart när PR-länk, testresultat och återstående blockerare är redovisade. En öppnad Codex-uppgift är inte en merge; en inloggad tjänst är inte ett verifierat flöde.

## Läs vid behov

- `references/status-och-aktivering.md`: daterad status per arm (ChatGPT-plan, Codex-miljöer, Cursor och Lenovo-begränsningar) och aktiveringssteg. Läs när en arm saknas, felar eller när användaren frågar vad som återstår.
