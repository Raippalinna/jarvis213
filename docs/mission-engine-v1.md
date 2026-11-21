# JARVIS Mission Engine v0.1 — säker planeringskärna

Status: **LOKAL KOD / EJ DRIFTSATT**. Motorn är deterministisk och nyckelfri.

## Syfte

Förhindra att agentiska planförslag blandas ihop med utförd, verifierad drift. Denna version producerar en stegvis uppdragsplan för intake → research → evidens → arkitektur → kod → test → review → release och planerar valfritt Creative/Slack-steg. Fler agentroller betyder inte att agenter körts.

## Användning

- Anropa \`plan_mission("Färdigställ Jarvis", connector_statuses={"github": "e2e_verified"})\` via Python. Körning är alltid dry-run.
- \`connector_statuses\` är explicit indata, aldrig autodetekterade. Endast \`e2e_verified\` räknas som tillgänglig. Även då utförs inga verktygsanrop.
- All offentlig sökning kräver separat granskad, sanerad fråga; användarens råa uppdrag exporteras aldrig av denna modul.
- Externa skrivningar, driftsättning, utskick och generering med okänd kostnad blockeras och kräver godkännande från ett framtida, fristående approvals-API.
- \`assess_receipt()\` returnerar högst \`eligible_for_external_review\`, aldrig "verifierat". Kräv autentiserad läsback från GitHub/Vercel/Notion, källkontroll och oberoende granskning innan UI säger "klart".
- Inga API-nycklar, webbläsaråtgärder, driftinställningar, modeller, budgetar, schemaändringar eller automatiska workflows aktiveras.

## Test

\`python -m pytest tests/test_mission_planner.py -q\`

## Säker fortsättning

1. Anslut en read-only Mission Queue i dashboarden, separerad från chatlogg.
2. Implementera adaptergränssnitt med deterministiskt approval-gate, idempotency-key, rate-limit och rollback.
3. Lägg till end-to-end-förtest mot redan godkända connectors i isolerad miljö; förvara bevis separat och verifiera källor.
4. Lägg till faktisk exekvering först efter explicita, åtgärdsspecifika godkännanden.

Återställning: ta bort \`src/jarvis/missions/\`, \`tests/test_mission_planner.py\` och \`docs/mission-engine-v1.md\` från ändringsgrenen.
