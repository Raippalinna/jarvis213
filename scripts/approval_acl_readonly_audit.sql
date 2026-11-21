-- P0 #52: skrivskyddad inventering av Approval Center-behörigheter.
-- Kör endast med behörig read-only SQL-session. Inga produktionsändringar.
-- Returnerar metadata, aldrig tabellrader, användaruppgifter eller hemligheter.
-- Kör om efter godkänd cutover och jämför resultaten manuellt.
BEGIN READ ONLY;
WITH targets(table_name) AS (
  VALUES ('approval_decision'), ('approval_request'), ('approval_audit_log')
),
roles(role_name) AS (VALUES ('anon'), ('authenticated'), ('service_role'))
SELECT t.table_name, r.role_name,
       has_table_privilege(r.role_name, format('%I.%I', 'public', t.table_name), 'SELECT') AS can_select,
       has_table_privilege(r.role_name, format('%I.%I', 'public', t.table_name), 'INSERT') AS can_insert,
       has_table_privilege(r.role_name, format('%I.%I', 'public', t.table_name), 'UPDATE') AS can_update,
       has_table_privilege(r.role_name, format('%I.%I', 'public', t.table_name), 'DELETE') AS can_delete
FROM targets t CROSS JOIN roles r
WHERE to_regclass(format('%I.%I', 'public', t.table_name)) IS NOT NULL
  AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.role_name)
ORDER BY t.table_name, r.role_name;

SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('approval_decision', 'approval_request', 'approval_audit_log')
  AND c.relkind IN ('r','p')
ORDER BY c.relname;

SELECT tablename, policyname, roles, cmd, permissive,
       qual AS using_expression, with_check AS check_expression
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('approval_decision', 'approval_request', 'approval_audit_log')
ORDER BY tablename, policyname;
COMMIT;
