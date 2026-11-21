-- READ ONLY. Inventory privileges and RLS for public.team_invites.
-- Safe to run against production: no row data, emails or tokens are selected.
-- Run before and after an independently approved cutover, compare snapshots.
SELECT current_timestamp AS checked_at,
       n.nspname AS schema_name,
       c.relname AS table_name,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS force_rls
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname = 'team_invites'
  AND c.relkind IN ('r','p');

SELECT role_name,
       has_table_privilege(role_name, 'public.team_invites', 'SELECT') AS can_select,
       has_table_privilege(role_name, 'public.team_invites', 'INSERT') AS can_insert,
       has_table_privilege(role_name, 'public.team_invites', 'UPDATE') AS can_update,
       has_table_privilege(role_name, 'public.team_invites', 'DELETE') AS can_delete,
       has_table_privilege(role_name, 'public.team_invites', 'TRUNCATE') AS can_truncate,
       has_table_privilege(role_name, 'public.team_invites', 'TRIGGER') AS can_trigger
FROM (VALUES ('anon'), ('authenticated'), ('service_role')) AS roles(role_name);

SELECT grantee, column_name, privilege_type
FROM information_schema.role_column_grants
WHERE table_schema = 'public' AND table_name = 'team_invites'
  AND grantee IN ('anon','authenticated','service_role')
  AND column_name IN ('email','token','role','team_id','invited_by','accepted_at')
ORDER BY grantee, column_name, privilege_type;

SELECT policyname, roles, cmd, permissive, qual, with_check
FROM pg_policies
WHERE schemaname = 'public' AND tablename = 'team_invites'
ORDER BY policyname;

SELECT trigger_name, event_manipulation, action_timing, action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public' AND event_object_table = 'team_invites'
ORDER BY trigger_name;

-- Summarize RPC names/signatures/EXECUTE grants, NEVER function source or credentials.
SELECT p.proname, pg_get_function_identity_arguments(p.oid) AS signature,
       p.prosecdef AS security_definer,
       has_function_privilege('anon', p.oid, 'EXECUTE') AS anon_execute,
       has_function_privilege('authenticated', p.oid, 'EXECUTE') AS authenticated_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND (p.proname ILIKE '%invite%' OR p.proname IN ('is_team_owner','is_team_member'))
ORDER BY p.proname;
