# JARVIS secure RC — explicit path from blocked to verified production

**Branch:** integration/jarvis-security-rc-20261106 · **PR #60 (draft)**.
**Scope:** Main JARVIS only. This branch combines the exact non-overlapping file
versions from #37, #45, #47, #49, #55 and adds a new owner-authenticated
Approval Center. It does not merge any of those PRs or change live services.

## Verified starting point

- Connected Supabase project: fzmnqvmfilqizzftphbt, active.
- Metadata-only query found 0 registered Auth users (at inspection time).
- Approval decision, request and audit tables have RLS but anon table grants
  including INSERT/UPDATE and permissive INSERT policies. RLS alone is insufficient.
- The live Comet and dashboard Edge Functions still used legacy versions.
- One human principal (11111111-1111-1111-1111-111111111111) and one agent
  principal (22222222-2222-2222-2222-222222222222) share tenant
  00000000-0000-0000-0000-000000000001; these are DB identities, not Auth users.
- No credentials, customer rows, tokens, emails or external production writes were read.

## New secure path and minimum release dependencies

1. **Additive DB stage:** independently review and apply
   docs/security/sql/01_approval_backend_staging.sql to a staging database.
   It creates public.jarvis_approval_admin (RLS enabled, no anon/auth table
   access) and two backend-only, atomic RPCs. It does not change legacy grants.
2. **Owner Supabase Auth:** set the safe public VITE_SUPABASE_PUBLISHABLE_KEY
   for the dashboard and confirm the email OTP template/provider settings.
   The **Beslut** tab uses OTP to sign in, then sends only Supabase Auth JWT
   to a distinct Approval endpoint. JWT exists in JS memory only. An owner
   must verify the new Auth user's ID out-of-band and execute
   docs/security/sql/03_owner_enrollment_after_auth.sql after explicitly
   replacing its NULL UUID. The first signup is NEVER auto-elevated.
3. **Edge staging:** deploy the *new* jarvis-approval-admin function to the
   approved staging environment with verify_jwt=true. Configure
   JARVIS_APPROVAL_ALLOWED_ORIGINS with the exact dashboard origin.
   Use backend SUPABASE_SECRET_KEY / legacy SERVICE_ROLE_KEY only in server
   secrets. The browser must never receive these. Missing config and missing
   admin mapping must return 503/403, not a silent bypass.
4. **Atomic request creation:** approve migration of the updated
   src/jarvis/approval/gate.py only after stage 01 exists. For R2/R3 it
   calls jarvis_approval_open exactly once. The RPC inserts decision,
   request and audit in one DB transaction and stores SHA256 of canonical
   task/session/tenant/risk with a 24-hour expiry. A missing RPC keeps R2/R3
   stopped. No model output may grant approval.
5. **Atomic owner decision:** the Approval Edge verifies Authorization
   against /auth/v1/user using the publishable key and checks the enabled
   admin mapping. It never trusts client-supplied actor/tenant. The SQL
   jarvis_approval_decide RPC transactionally locks the pending request,
   enforces scope, expiry, action hash and R2/R3 status, then writes the
   decision and audit atomically. A second attempt fails; approval does
   NOT automatically execute or deploy anything.
6. **Execution readback gate:** privileged execution adapters must call
   jarvis_approval_check with request ID, tenant and canonical action hash,
   and proceed only when it returns true. The Python ApprovalGate exposes
   is_approved(...) to do this check; the production executor must still
   independently enforce capability, cost, kill switch, idempotency and
   provider receipts. Approval alone is NOT authorization to skip these.
7. **Migrate old consumers:** inspect and migrate jarvis-core MCP prototype,
   jarvis-core n8n decision sync, existing Approval dashboards, GitHub-runner
   gate and other clients from anonymous writes to a verified server role.
   Require real role and tenant tests. No blanket anon revoke beforehand.
8. **Credential/auth integration:** stage #37 server-key preflight and
   #45 dashboard header-only auth. Migrate Comet clients from GET ?k= to
   header-only POST before deploying #47. Rotate any key that appeared
   in a URL/log. Verify stopped autonomy and unknown-policy behavior.
9. **Cutover:** save a fresh private grant+policy snapshot. Only after
   staging read/write/expiry/unauthorized/cross-tenant tests succeed,
   obtain separate operator approval for
   docs/security/sql/02_approval_grants_cutover.sql and deploy in a
   controlled window. It revokes anon/auth table grants on approval
   records and removes the permissive approval policies. It intentionally
   does NOT blanket-revoke jarvis_memory, because this shared database
   may serve other applications. Investigate memory permissions separately.
10. **Final release gate:** after staging security pass, authenticated
   receipt/readback, kill-switch and cost/permission enforcement, the
   owner may approve merge, migration and deployment as distinct actions.
   Agent Orchestra remains execution_enabled=false by default.

## Evidence: offline vs operational

- GitHub Actions checks Python tests, JavaScript mock API tests, dashboard
  TypeScript/build and synthetic orchestrator. Their PASS means only that
  the repo release candidate passed those checks at that exact SHA.
- SQL files have not been applied; live endpoints have not been deployed.
  No valid Auth user was enrolled when the inspection was performed.
- Database RPCs require staging SQL syntax, transaction, privilege,
  negative-role and concurrent-double-approval tests against PostgreSQL
  before any cutover is authorized.
- Public browser OTP requires Supabase email provider delivery settings.
  The dashboard will show configuration errors rather than claim success.

## Rollback strategy

- No DB changes have been made by this PR. Closing the draft leaves main
  and live production unchanged.
- After an approved stage rollout, revert or disable the newly deployed
  Approval Edge first if necessary (it never executes actions), disable
  the owner mapping and block subsequent decisions, then restore from a
  reviewed DB migration backup if appropriate. Never blindly restore
  anonymous write privileges merely to make a broken client work.
- Keep a verifiable run ID for the entire source -> approval -> action ->
  audit -> external readback chain, and do not claim finished execution
  without it.
