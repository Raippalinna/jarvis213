# JARVIS Mission Engine — offline, säker uppgiftskö (2026-11-05)

`src/jarvis/core/mission_engine.py` tillför en deterministisk kö för avgränsade uppdrag: beroendegraf (DAG), kontroll av cykler, färdig-/väntelägen, begränsade omförsök, säkra avbrott och revisionshändelser. Ingen modell, worker, databas eller extern API anropas av modulen.

## Exempel

```python
from jarvis.core.mission_engine import MissionQueue, Step

mission = MissionQueue("example-001", (
    Step("inspect", "Granska källan", risk_class="R0"),
    Step("patch", "Förbered kodpatch", ("inspect",), risk_class="R1"),
    Step("publish", "Extern publicering", ("patch",), risk_class="R2"),
))
assert mission.ready() == ["inspect"]
lease = mission.claim("inspect")  # reservation, inte exekvering
mission.finish("inspect", lease["attempt"], success=True)
```

## Säkerhetskontrakt

- **Inte ett verktyg för exekvering.** `claim()` reserverar bara ett steg. Den betrodda klienten måste kontrollera användarens behörighet, riskklass och idempotens före varje extern effekt.
- Riskklass är **indata**, inte en säker riskbedömning. Caller får inte låta användare eller LLM godtyckligt nedgradera R2/R3 till R0/R1. Vid okänd risk används R2 som standard.
- R2/R3 kräver en extern `approval_check` vid varje reservation. Saknas eller underkänns den spärras reservationen. Integrera med verkligt Approval Center och kontrollera besluts-ID, tenant, handling, giltighet och aktuell status innan verklig exekvering.
- **Ingen crash-safe ledger ännu.** Tillstånd ligger i minnet. Kör inte sidoeffekter autonomt eller återspela steg efter omstart utan beständig logg, idempotensnycklar och avstämning av tidigare resultat.
- Avbrott stoppar nya reservationer och ignorerar senare avslutsrapporter; det återkallar inte redan utförda externa åtgärder.
- Inget ändrat i `ApprovalGate`, `DRY_RUN`, kill switch, budget, Supabase, Vercel eller Perplexity OAuth.

## Acceptans och nästa integration

Kör `python -m pytest tests/test_mission_engine.py -q` samt hela befintliga testsuiten via kvalitetsgrinden i PR #38. Nästa steg är autentiserat adapterskikt till befintlig supervisor och Approval Center, beständig state store med idempotens och driftkontroll. Gör ingen production deploy utan separat verifiering och godkännande.

Rollback: stäng PR eller ta bort den isolerade Python-filen, testfilen och detta dokument.
