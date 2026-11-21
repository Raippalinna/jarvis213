-- Read-only catalog snapshot for JARVIS Approval Center security review.
-- No user rows, API keys, transaction writes or SQL functions are executed.
-- Run only from an authorized SQL connection; keep the output private.
WITH monitored(table_name) AS (
  VALUES ('approval_decision'), ('approval_request'),
         ('approval_audit_log'), ('jarvis_memory')
),
checks AS (
  SELECT
    m.table_name,
    c.relrowsecurity AS rls_enabled,
    has_table_privilege('anon', c.oid, 'SELECT') AS anon_select,
    has_table_privilege('anon', c.oid, 'INSERT') AS anon_insert,
    has_table_privilege('anon', c.oid, 'UPDATE') AS anon_update,
    has_table_privilege('anon', c.oid, 'DELETE') AS anon_delete,
    has_table_privilege('authenticated', c.oid, 'INSERT') AS auth_insert,
    has_table_privilege('authenticated', c.oid, 'UPDATE') AS auth_update,
    has_table_privilege('authenticated', c.oid, 'DELETE') AS auth_delete,
    (SELECT count(*)::integer
       FROM pg_policies p
      WHERE p.schemaname = 'public'
        AND p.tablename = m.table_name
        AND p.cmd IN ('ALL', 'INSERT', 'UPDATE')
        AND ('anon' = ANY(p.roles) OR 'public' = ANY(p.roles))
    ) AS anon_or_public_write_policies
  FROM monitored m
  LEFT JOIN pg_namespace n ON n.nspname = 'public'
  LEFT JOIN pg_class c ON c.relnamespace = n.oid
                      AND c.relname = m.table_name AND c.relkind IN ('r','p')
)
SELECT COALESCE(jsonb_agg(to_jsonb(checks) ORDER BY checks.table_name), '[]'::jsonb)
FROM checks;
