# Live Supabase read-only security gate — 2026-11-06

**Project:** `fzmnqvmfilqizzftphbt` · **Snapshot:** read-only MCP queries · **Status:** Blocked for production release.

This report is intentionally limited to database metadata and advisor summaries, not rows or credential values.

## Observed

- Project `ACTIVE_HEALTHY`; `system_config.autonomy_enabled=true` (database state only).
- Four edge functions ACTIVE: `jarvis-comet`, `jarvis-dashboard-api`, `jarvis-brain`, `jarvis-kpi-snapshot`. **Do not assume these deployed versions include proposed PR #57 code.**
- `jarvis_dashboard_v2` has public RLS SELECT / ALL policies containing `auth.uid() IS NULL`, and `anon`/authenticated SELECT grants.
- `approval_request` allows INSERT in an anon/authenticated policy with `WITH CHECK (true)`.
- `event` and `memory_episode` contain fixed-tenant anonymous access policies, including writes.
- `jarvis_memory` policies contain `user_id IS NULL`; inspect effective grants before claiming anonymous read.
- `jarvis_chat` has RLS enabled with no policies; client operations may be blocked.
- Supabase Security Advisor: 140 GraphQL anon table schema-exposure warnings and 12 RLS-enabled/no-policy informational findings. Schema visibility does **not** establish row visibility.

## Release checklist (blocking)

- [ ] Inventory all SQL privileges including view/function RPC access, direct browser/GraphQL users, and dependent services.
- [ ] Stage exact reversible RLS and grant changes; preserve legitimate app paths without anonymous global access.
- [ ] Test authorized/unauthorized users, missing JWT, foreign tenants and attempts to mutate approval requests.
- [ ] Verify CORS/Comet clients use new POST + header contract before any Edge Function deploy.
- [ ] Verify `jarvis-dashboard-api` and `jarvis-comet` actual deployed code revision matches release candidate.
- [ ] Run supervised read-only auth preflight with valid protected key, then staged negative/positive tests.
- [ ] Review exact SQL, approve separately, apply and re-check advisors. No production SQL change is part of this PR.

## References

- [Jarvis core P0 RLS issue #3](https://github.com/rickyraippalinna/jarvis-core/issues/3)
- [Jarvis integration PR #57](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/57)
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [GraphQL anon schema visibility](https://supabase.com/docs/guides/observability/advisors?lint=0026_pg_graphql_anon_table_exposed)
- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)

**Do not treat passing offline GitHub CI as live tenant isolation or production-readiness.**
