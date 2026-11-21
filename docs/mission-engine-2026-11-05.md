# JARVIS Mission Engine – bevisstyrd uppgiftsmotor

## Mål och avgränsning

Detta är en deterministisk, nyckelfri kärnkomponent för huvud-Jarvis. Modulen src/jarvis/core/mission_engine.py modellerar steg, beroenden, förmågor, godkännanden och verifieringsbevis.

Den kör inte externa åtgärder. Den ändrar inte befintlig Supervisor, Approval Center, DRY_RUN, kill switch, budget, modellrouting, databas, e-post eller deployment. Funktionen aktiveras inte automatiskt i drift.

## API-kontrakt

- MissionStep deklarerar varje steg och dess beroenden, required_capabilities samt approval_id.
- MissionEngine kontrollerar planen för tomma steg, dubletter, okända beroenden och cykler.
- ready() och start() vägrar fortsätta utan verifierade föregångare, rätt capabilities och uttryckliga approvals.
- submit() tar emot ExecutionEvidence med artefakthänvisning och resultatbeskrivning. Ett inskickat påstående räknas INTE som verifierat.
- verify() använder en av anroparen implementerad betrodd callback. Endast en framgångsrik kontroll som returnerar en icke-tom bevisreferens kan ge status verified.
- fail(), retry() och cancel() hanterar misslyckanden, manuell fallback och avbrutna uppdrag.
- snapshot() återger bara status och kvittoindikatorer, inte råa svar, felsträngar eller tokens.

## Kör och testa

Kommandot för isolerad verifiering är:
python -m pytest tests/test_mission_engine.py -q

Kodexempel:

    from jarvis.core.mission_engine import MissionEngine, MissionStep, ExecutionEvidence
    mission = MissionEngine([
        MissionStep("test", "Kör tester", required_capabilities=("local_test",)),
        MissionStep("review", "Granska ändring", depends_on=("test",), approval_id="owner_review"),
    ])
    assert mission.ready(capabilities={"local_test"}) == ("test",)
    mission.start("test", capabilities={"local_test"})
    mission.submit("test", ExecutionEvidence("ci-run:123", "Testresultat mottaget"))
    # Kontrollera kör-ID mot betrodd CI-tjänst i egen verifierare.
    ok = mission.verify("test", verifier=trusted_ci_verifier)
    assert ok
    assert mission.gate("review") == "missing_approval"

trusted_ci_verifier är avsiktligt INTE implementerad här: ingen verklig CI-, OAuth- eller produktionsanslutning kan antas. Ett verkligt kvitto måste kontrolleras externt. Godkännande får inte skapas av LLM-text.

## Verifiering och kvarvarande arbete

15 isolerade pytest-tester och Python-kompilering har körts lokalt den 5 november 2026. Full repositoriesvit, skyddad Supabase-backend, Perplexity Computer OAuth och verkliga verktygsåtgärder är ej verifierade. GitHub CI-status måste kontrolleras på exakt slutlig PR-head.

För att slå på uppgiftsmotorn i skarp drift krävs en separat adapter som hämtar capabilities ur autentiserade verktyg och approvals från befintlig deterministisk Approval Center-kod. Även DRY_RUN, kostnadstak och tenantisolering ska upprätthållas.

## Återställning

Stäng PR-utkastet utan merge. Om funktionen senare mergas räcker revert av dessa tre nytillagda filer. Ingen databasåterställning krävs.
