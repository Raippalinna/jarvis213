# JARVIS Approval Center — verified exposure and controlled cutover

**Status 2026-11-05:** Review-only security preflight, not a production remediation. No database, secrets, deployment, merge, or external messages were changed by this PR.

## Direct read-only evidence

The connected Supabase project `fzmnqvmfilqizzftphbt` was ACTIVE_HEALTHY. Catalog-only SQL queries showed `public.approval_decision`, `public.approval_request`, and `public.approval_audit_log` each had `anon` SELECT/INSERT/UPDATE/DELETE privileges, with RLS enabled. Of particular concern:

- `approval_decision` policies permit anonymous INSERT to a fixed tenant and anonymous UPDATE for that tenant. A fixed tenant constant is *not* user authentication.
- `approval_request` includes `anon,authenticated` INSERT with `WITH CHECK true`.
- `approval_audit_log` includes `anon,authenticated` INSERT with `WITH CHECK true`.
- `jarvis_memory` has an anonymous INSERT grant and a permissive non-secret INSERT policy. RLS does not imply denial.
- `jarvis_memory_search` has a mutable search_path advisory; investigate separately.
- A database grant alone does **not** prove effective access to every row. The combined grants and permissive policies establish a concrete authorization risk; no exploit or customer-data read was attempted.

Read-only checks and Supabase Security Advisor were used. No secret values or customer records were retrieved.

## Dependencies that must be inventoried

1. `jarvis-omega-v2/src/jarvis/approval/gate.py` writes pending decisions, requests and audit events. PR #37 supplies modern backend-key handling but live backend preflight was skipped.
2. `jarvis-core/comet/jarvis-mcp-server.ts` contains an approval reader and decision writer; the prototype is previously flagged as blocked/unverified, so do not assume it is safe or inactive without confirmation.
3. `jarvis-core/workflows/n8n/jarvis-n8n-notion-decision-sync.json` contains a decision-table writer. Check the credential role and actual deployment.
4. UI, Perplexity Computer, Retool, and any other consumers must be assessed before removing client access.

## Reviewed cutover sequence (no automatic SQL migration)

1. Keep autonomous R2/R3 execution **disabled**. Verify server-side kill switch is enforced across all dispatch paths. Never accept a user-supplied tenant or an approval ID as sufficient proof.
2. Replace all anonymous Approval Center writes with a narrow, authenticated server endpoint. Validate verified principal, tenant ownership, action hash, expiry, current status, and allowed transitions. Use a privileged key exclusively on the server; prefer an atomic transaction for decision + request + audit.
3. Confirm #37 backend credential checks, #47 Comet header-only dispatch, and #45 dashboard authentication with staging tests. Rotate any credential known to have appeared in URLs or logs.
4. Take a *fresh* metadata-only baseline with `scripts/security/approval_acl_snapshot.sql`; save its single JSON output privately and run `python scripts/security/check_approval_acl.py snapshot.json`. This deliberately fails against the observed unsafe permissions.
5. After authenticated clients are proven to work, create a **separately reviewed migration** for least-privilege grants and RLS. Target: no anonymous grants on the four private tables, no anonymous/public write policies; no `authenticated` write grants to approval tables unless separately justified with verified authorization. Do not simply widen RLS or use `SECURITY DEFINER` to make errors disappear.
6. Stage the migration. Prove anonymous writes and cross-tenant writes are denied; authorized server requests, audit readback, rejection, expiry, retry/idempotency, and kill switch behave correctly. Repeat the catalog snapshot and require a passing checker result.
7. Obtain a **separate explicit production approval** naming the migration and rollback. Deploy with monitoring; verify database privileges, client functionality, and run-ID receipts. If clients break, restore only the reviewed minimum access while fixing their authentication. Do not restore broad anonymous writes.

## Automated and non-automated evidence

The Python checker is a *local, fail-closed assessment of an input snapshot*, not an on-demand live scan. The SQL file is SELECT-only and does not inspect table contents. Passing synthetic tests does not clear production. A pass is meaningful only against a fresh, trustworthy SQL result, plus negative API tests and a verified authorized end-to-end request.

The checker intentionally requires all monitored tables to deny anonymous table grants, even where RLS might block access. This is a defense-in-depth release target, not a claim that every existing grant leads to readable private data.

## Reversal

This PR can be closed without any operational effect. No SQL migration is executed by CI or on merge. For any future staged migration, store before-state grants/policies securely and write a separately reviewed rollback. Do not auto-restore anonymous write access.
