-- PREPARED ONLY. Production security change requires explicit approval.
-- Observed target: Supabase fzmnqvmfilqizzftphbt, 2026-09-21.
-- Removes the six observed permissive client policies; no data deletion.
-- This intentionally disables direct anonymous/client review UIs.
BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class
    WHERE oid IN ('public.approval_decision'::regclass,
                  'public.approval_request'::regclass,
                  'public.approval_audit_log'::regclass)
      AND NOT relrowsecurity
  ) THEN
    RAISE EXCEPTION 'Approval RLS must already be enabled';
  END IF;
END
$$;
DROP POLICY IF EXISTS jarvis_anon_tenant_insert ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_anon_tenant_select ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_anon_tenant_update ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_backend_insert_pending ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_backend_insert_request ON public.approval_request;
DROP POLICY IF EXISTS jarvis_backend_insert_audit ON public.approval_audit_log;
-- Preserve service-role policies, table grants, decisions and audit history.
-- Fail closed on policy drift rather than claiming the intended isolation.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename IN ('approval_decision', 'approval_request',
                        'approval_action', 'approval_audit_log')
      AND roles && ARRAY['public', 'anon', 'authenticated']::name[]
  ) THEN
    RAISE EXCEPTION 'Unexpected remaining Approval client policy; manual review needed';
  END IF;
END
$$;
COMMIT;
