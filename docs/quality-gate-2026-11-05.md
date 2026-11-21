# JARVIS kodkvalitet — körbar kvalitetsgrind, 2026-11-05

Källa: [Notion-färdigheten jarvis-kodkvalitet](https://app.notion.com/p/40f66d43c10781be95d3f10d8d6d214c). Färdigheten beskriver förfarandet och är **inte** i sig ett CI-system. Denna ändring tillför `.github/workflows/jarvis-code-quality.yml` till det kanoniska repot för **huvud-Jarvis**. Inga andra Jarvis-instanser eller appar skapas.

## Körbara acceptansprov

| Kontroll | Exakt körning | Värde |
| --- | --- | --- |
| Python – samtliga tester | `env -u PYTHONPATH python -m pytest tests -q --disable-socket --allow-unix-socket --junitxml=pytest-results.xml` | Testar logik, fallbacks och gränser utan extern nätverksåtkomst |
| Syntax | `python -m compileall -q src scripts jarvis_cloud.py` | Stoppar syntaxfel i kärnan |
| JS/API-fixtures | `node --test tests/*.mjs` | Testar edge-kod med mockad nätverksväg |
| Dashboard, TypeScript och bygg | `cd apps/dashboard && npm ci --ignore-scripts && npm run build` | Verifierar att klienten byggs och TypeScript-kontroll i byggskriptet passerar |
| Samlad status | `quality-gate` kräver att alla tre jobb har resultat `success` | Fel, avbrutet eller hoppat över = underkänt |

**Körningar är isolerade:** inga AI-modell-anrop, mail, Slack/Notion-skrivningar, driftåtgärder eller GitHub secrets i dessa tester. Python-fixtures blockeras från nätverk. JavaScript-testerna använder intern `vm`-mock, utan verkliga fetch-anrop. Beroenden installeras från pakethanterare före testerna.

## Vad PASS INTE betyder

- Produktionsdriftsättning, Perplexity Computers OAuth-anslutning, autentiserat chat-flöde, tenant-/RLS-isolering eller godkännandekedjor är **inte verifierade i drift** av workflowet.
- `live-read-only-preflight` i [PR #25](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/25) är fortfarande ett separat skyddat prov som kräver ägargodkända backendnycklar. Grön `unit-tests` med hoppad live-preflight får inte kallas godkänd backend.
- Den separata [nyckelfria API-kontrollen](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42111613758) verifierade att anonyma anrop avvisas med 401; det bevisar inte att giltig auth lyckas.
- Repots branch protection måste separat kräva `quality-gate` som statuscheck för att göra en grön grind formellt **obligatorisk** före merge. Den här PR:n ändrar inga behörigheter eller branch rules.
- `npm run build` gör TypeScript-kontroll men ingen separat ESLint-körning (dashboarden saknar lint-script). Registrera detta som **ej kört**, inte PASS.

## Säker process

1. Granska diffen i separat PR och jämför med överlappande PR:er.
2. Kör PR-workflowet och läs resultat för **exakt head SHA**; JUnit-sammandrag utan känsliga felsträngar sparas som artifact.
3. En fail på någon del blockerar `quality-gate`. Rätta i samma gren och kontrollera ny SHA.
4. Efter godkännande av ansvarig kan ändringen sammanfogas. Kör inte migration, produktions-deployment eller nya integrationer i detta CI-flöde.
5. För en verklig Perplexity-/ChatGPT-koppling krävs separat auktoriserad MCP/OAuth, ett ofarligt fullföljt uppdrag och verifierad återläsning av rätt uppgifts-ID.

Återställning: stäng PR utan merge, eller gör revert på CI-filen och dokumentationen efter godkännande. Kod för Approval Center, DRY_RUN, modellbudget, leverantörer och database har inte ändrats.
