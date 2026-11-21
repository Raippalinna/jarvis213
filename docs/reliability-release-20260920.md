# Jarvis reliability update

Continuation: [API and safety completion](completion-api-safety-20260920.md)
supersedes the open-gate list below where the Python guard, scoped text memory
and routing veto are now implemented. The remaining production gates are listed
there; neither document is a production-deployment claim.

## Scope

Improve the existing Jarvis, not construction estimates or unrelated apps.
The project-level prompt and the installed connector-map skill are separate
from this Python release. Saving those settings does not deploy this branch.

## Changes

- Explicit succeeded/failed status, with approval holds distinguished.
- Empty, truncated and error-marked responses try the next eligible candidate.
- Failed runs skip normal memory, quality audit and Notion briefing delivery.
- Failed runs, approval holds and failed requested delivery have distinct exit codes.
- Runtime fallback rechecks model, configured floor, estimated cost and data policy.
- Highest detected sensitivity wins; detected secrets are not stored as chat memory.
- Retrieved context is reference data, not part of the system instruction.
- Prompt explicitly distinguishes prepared text from executed tool actions.
- Provider errors no longer copy raw exception content into generated answers.
- Provider calls have bounded timeout and output tokens.
- GitHub inputs are parsed as JSON, not inserted into executable shell text.
- Offline unit tests cover control flow without real credentials or network calls.

## Reproduce

```sh
python -m pip install -r requirements.txt
PYTHONPATH=src:. python -m unittest discover -s tests -v
```

The workflow `Jarvis offline regression tests` uses Python 3.11, no application
secrets, and runs on this improvement branch. It does not call production Jarvis.

## Release gates still open

This is not proof of end-to-end operation. Before production promotion:

1. Review the branch diff and approve the exact production scope.
2. Verify live model availability and request compatibility for each configured provider.
   Provider catalog prices and quality indexes are configuration assumptions, not fresh measurements.
3. Enforce the Supabase kill switch at every runtime side-effect boundary; the existing
   Python runtime does not yet consistently enforce it. A true database flag is not enforcement.
4. Replace keyword-only approval decisions with typed action authorization.
   Topic words can overblock harmless drafting; missing synonyms can underblock actions.
5. Classify each retrieved memory/Notion/wiki item before provider selection.
   The new text scan is a limited heuristic, not a full data-loss-prevention system.
6. Verify requested Notion delivery by reading the resulting object, not only the HTTP response.
7. Verify real budget metering. Configured estimates and token caps are not a billing guarantee.
8. Audit memory tenancy/RLS and raw task logging; secret detection is not exhaustive.

Do not disable approval gates or raise spending limits to make a smoke test pass.
No production test or scheduled-task change is included in this release.

## Rollback

Until promotion, production code is unchanged: leave main untouched and do not merge.
After an approved promotion, revert the specific release commit and rerun the offline tests.
The previous project prompt is retained separately in `project-instructions-before.md`;
restore it through Project settings if needed. Do not replace global account instructions.
