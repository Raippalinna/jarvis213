-- Approval Center: remove public/anon direct table access only after an owner exists.
-- Prepared for review. The preflight deliberately aborts on the current production state
-- (zero enabled jarvis_approval_admin memberships) so this cannot lock out the owner flow.

DO $preflight$
BEGIN
  IF to_regclass('public.jarvis_approval_admin') IS NULL THEN
    RAISE EXCEPTION 'Approval lockdown blocked: jarvis_approval_admin table is missing';
  END IF;

  IF to_regprocedure('public.jarvis_approval_decide(uuid,uuid,text,text)') IS NULL THEN
    RAISE EXCEPTION 'Approval lockdown blocked: owner decision RPC is missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM public.jarvis_approval_admin
     WHERE enabled IS TRUE
  ) THEN
    RAISE EXCEPTION
      'Approval lockdown blocked: provision and verify at least one owner-authenticated jarvis_approval_admin membership first';
  END IF;

  IF NOT has_function_privilege(
    'service_role',
    'public.jarvis_approval_decide(uuid,uuid,text,text)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Approval lockdown blocked: service_role cannot execute the owner decision RPC';
  END IF;
END;
$preflight$;

-- Remove direct client privileges. Existing server-side service_role access is preserved.
REVOKE ALL PRIVILEGES ON TABLE public.approval_decision
  FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.approval_request
  FROM PUBLIC, anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.approval_audit_log
  FROM PUBLIC, anon, authenticated;

-- Remove only the known anon/authenticated policies. Keep jarvis_service_all intact.
DROP POLICY IF EXISTS jarvis_anon_tenant_insert ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_anon_tenant_select ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_anon_tenant_update ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_backend_insert_pending ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_backend_insert_request ON public.approval_request;

-- The owner decision RPC remains server-only.
REVOKE ALL ON FUNCTION public.jarvis_approval_decide(uuid,uuid,text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.jarvis_approval_decide(uuid,uuid,text,text)
  TO service_role;

COMMENT ON TABLE public.approval_decision IS
  'Approval decisions: server-side writes only; direct anon/authenticated table access revoked after owner provisioning.';
COMMENT ON TABLE public.approval_request IS
  'Approval requests: server-side writes only; direct anon/authenticated table access revoked after owner provisioning.';
COMMENT ON TABLE public.approval_audit_log IS
  'Append-only approval audit trail; direct anon/authenticated access revoked.';
