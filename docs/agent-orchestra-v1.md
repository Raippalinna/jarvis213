# JARVIS Ω∞ — Agent Orchestra v1 (main Jarvis only)

## Status and security boundary

**Implementation:** agent catalog, deterministic orchestration graph, per-step risk/capability/approval gates, bounded retries, budget reservations, fail-closed evidence verification and read-only snapshots.

**Not implemented:** Perplexity OAuth handshake, authenticated live connectors, production execution, durable queue, tenant-aware receipts, provider spending reconciliation, live dashboard controls, deployment. A passing synthetic test is not a real-world delivery.

This adds a layer **on top of** `src/jarvis/core/mission_engine.py` merged in PR #40. It does not replace the existing LangGraph Supervisor, Approval Center, Frugality Agent, Supabase memory or the owner's kill switch. It does not switch on automatic actions.

## Agent roster (allowlist, not evidence of provider connectivity)

| Step | Agent role | Dependency | Permission / policy |
| --- | --- | --- | --- |
| intake | strategist | none | local |
| research | researcher | intake | sanitized reviewed query + authenticated external-read approval |
| evidence | verifier | research | authenticated trusted-source read |
| architecture | architect | evidence | local |
| implementation | coder | architecture | branch-only write capability + explicit action approval |
| testing | tester | implementation | offline test capability |
| review | independent_reviewer | testing (and creative when selected) | independent review-read capability |
| release | release_manager | review | deploy capability + separate explicit release approval |
| creative (optional) | creative_director | architecture | creative connector + cost / scope approval |
| notification (optional) | operations | review | approved outbound destination and send approval |

Future connectors can include GitHub, Firecrawl, Notion, Slack, Higgsfield and OpenArt, but **this code does not claim they are connected**. Every adapter must be authenticated separately and bound to the correct tenant.

## Programmatic dry-run

```python
from jarvis.core.agent_orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator(
    "Complete the main JARVIS agent orchestration",
    creative=True,
    notifications=True,
    budget_sek="1.00",
)
preview = orchestrator.snapshot()
assert preview["execution_enabled"] is False
assert preview["production_verified"] is False
```

Dry-run produces only metadata and an opaque random mission identifier; the private goal is not included or hashed into externally visible metadata. Mission IDs are not durable idempotency keys. It does **not** execute the model, fetch pages, create pull requests or send Slack messages.

## Future execution contract (trusted backend only)

`run_one()` is a low-level integration point intended for a future reviewed adapter layer. It is **not** safe to expose as a public HTTP endpoint.

Required in the caller *before* `execution_enabled=True` is ever used:

1. Authenticate principal, tenant and session with verified OAuth/JWT; never rely on model text, URL query keys or plain user-provided tenant IDs.
2. Resolve the current `autonomy_enabled` kill switch and fail closed on any error. Enforce R2/R3 Approval Center decisions with server-side readback, scope, expiry, action hash and owner identity. Merely supplying a matching approval string is not sufficient.
3. Obtain capabilities from the authenticated connector registry, not a parameter supplied by an agent. Independently review and declassify any external research query.
4. Enforce provider-side hard quotas and max spend on each API request. The in-memory `estimated_cost_sek` reservation is not billing reconciliation or a binding provider spending cap.
5. Provide role-matched adapters with strict allowlisted tools, timeouts, safe parsing, cancellation, no implicit retries and durable per-tenant idempotency keys. No raw secrets or private context in prompts sent to public sources.
6. Verify a receipt through a separate authenticated readback against the authoritative system and validate tenant + action + artifact hash. A self-reported success from an LLM or adapter is insufficient.
7. Persist a tamper-evident audit trail and a durable mission queue; implement crash recovery, replay protection, alerts and rollback before real multiagent execution.
8. Integrate the feature into the Supervisor and dashboard only behind a server-side feature flag and a staging end-to-end test. No bypass of existing approval_gate, Frugality or security controls.

`run_one()` executes **at most one** trusted adapter and leaves downstream steps blocked until independent verification succeeds. Every invocation requires a backend-owned `autonomy_check`. Capability-bearing steps additionally require `capability_check`; external work additionally requires `approval_check`; estimated-cost steps require `spend_check`. The callbacks must independently read authenticated grants: **never implement them with an agent-supplied Boolean, approval ID or untrusted action string**. Missing, stale, or failing checks fail closed. Exceptions are masked from snapshots. There is no autonomous self-registration of permissions and no permission inference from prompts.

## Validation and release sequence

```bash
python -m pytest -q tests/test_agent_orchestrator.py tests/test_mission_engine.py
python -m py_compile src/jarvis/core/agent_orchestrator.py
```

The read-only GitHub Actions job `jarvis-agent-orchestration.yml` runs these offline without credentials. Required before merge: security review, green CI on the final head, tests for multi-tenant and authenticated decisions when adapters exist. Required before deploy: Supabase backend preflight (#13 / PR #37), Comet header/tenant/autonomy fix (#43 / PR #47), dashboard auth migration review (#45), staged Perplexity OAuth bridge, observed costs and tested kill switch. Do not stack the overlapping dashboard PRs #42/#44/#45 blindly.

## Rollback

The new functionality is isolated: remove `src/jarvis/core/agent_orchestrator.py`, its tests, the new workflow and this document. No schema, settings, secrets, production services, or current Supervisor execution path are modified by this change.
