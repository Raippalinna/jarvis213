# Pontura ↔ JARVIS: isolation-first handoff contract v1

**Status: code on review branch, NOT wired to active GitHub Actions / Perplexity / n8n / Supabase.** This is a reviewed boundary, not a verified live connection.

## Existing Jarvis mechanisms reviewed
- `src/jarvis/agents/frugality.py`: quality gates, cost vetoes, pre/post-flight audit.
- `src/jarvis/routing/tiers.py`: tier and sensitivity routing. **Do not reuse its unconditional final fallback on confidential jobs**; Pontura rejects such jobs instead.
- `jarvis_cloud.py`: GitHub Actions execution and optional Notion posting. Not activated for Pontura.
- `jarvis-core/workflows/n8n/`: webhooks to Jarvis-owned records. Do not copy their credentials, existing data destinations or customer data.
- Another private `perplexity-os` repository concerns a different personal context. **Excluded entirely.**

## Contract
`bridge_contract.py:validate_draft` accepts a strict `pontura.jarvis.v1` JSON envelope:

`contract_version`, `origin`, `project`, `tenant_id`, `request_id`, `action`, `source_ids`, `sensitivity`, `estimated_cost_sek`, `status`, `provenance`.

Allowed actions: source_review, maintenance_summary, opportunity_assessment, cost_estimate. All proposals remain **draft** and are strictly non-executing.

- Default estimated-cost ceiling: **0 SEK**, avoid unapproved network/model calls.
- Public/internal metadata only, *no customer content* or secrets.
- The tenant name is **checked against an authorized server-side parameter**, never trusted from the envelope alone.
- Source references and pinned Git commit string are only syntax checked; they are **not source authenticity proofs**.
- Fingerprints support local dedup, but the production backend must add replay prevention, authenticated origin and a genuine write-protected audit log.
- Pontura decides whether a source is verified; Jarvis labels do not override Pontura's source policy.

## Local tests
`python -m unittest discover -s integrations/pontura -p 'test_*.py' -v`.

## Go-live controls
1. Build separate Pontura GitHub repository and isolated backend; Auth and RLS, two-tenant access tests.
2. Add an authenticated server-only ingress (no browser tokens). Bind verified client identity to one tenant and enforce replay protection/idempotency on persisted `request_id`.
3. Validate exact source IDs/versions in **Pontura**, then store **draft** in Pontura Approval Center with server audit.
4. Never auto-approve, email, import, schedule billable actions or change Jarvis main runtime without a separate reviewed release.
5. Inspect actual Pontura Perplexity project contents with legitimate saved login before authorizing sync.

## Current verified links
- Pontura Notion control: https://app.notion.com/p/41166d43c107816d98a4c198ce6f7b57
- Perplexity Pontura (access not verified): https://www.perplexity.ai/projects/09dba2a5-72dd-46e6-938f-001e9321c61e
- Pontura QA Lovable (not published): https://lovable.dev/projects/59504bf6-f272-47a6-88f0-2a57303d3af8
- Prior merged **documentation-only** Jarvis PR: https://github.com/rickyraippalinna/jarvis-omega-v2/pull/72

No actual tokens, private documents or operational customer details are contained here.
