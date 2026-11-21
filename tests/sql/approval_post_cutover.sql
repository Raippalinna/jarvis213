-- Must PASS only after the guarded cutover was explicitly enabled in
-- the synthetic CI test runner. No production change involved.
\set ON_ERROR_STOP on
DO $test$
DECLARE tabname text;
BEGIN
    FOREACH tabname IN ARRAY ARRAY['approval_decision','approval_request','approval_audit_log']
    LOOP
        IF has_table_privilege('anon','public.'||tabname,'SELECT')
           OR has_table_privilege('anon','public.'||tabname,'INSERT')
           OR has_table_privilege('anon','public.'||tabname,'UPDATE')
           OR has_table_privilege('anon','public.'||tabname,'DELETE')
           OR has_table_privilege('authenticated','public.'||tabname,'INSERT')
           OR has_table_privilege('authenticated','public.'||tabname,'UPDATE')
        THEN
            RAISE EXCEPTION 'unsafe grants survived cutover: %',tabname;
        END IF;
    END LOOP;
    IF EXISTS (SELECT 1 FROM pg_policies p WHERE p.schemaname='public'
       AND p.tablename IN ('approval_decision','approval_request','approval_audit_log')
       AND p.policyname LIKE 'jarvis_anon%')
    THEN RAISE EXCEPTION 'anonymous approval policy survived cutover'; END IF;
    IF NOT has_function_privilege('service_role',
        'public.jarvis_approval_check(uuid,uuid,text)','EXECUTE')
    THEN RAISE EXCEPTION 'trusted backend lost readback capability'; END IF;
END $test$;
