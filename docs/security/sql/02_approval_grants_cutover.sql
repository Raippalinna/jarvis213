-- DO NOT RUN UNTIL signed-in admin, backend RPC, n8n/MCP inventory and staging tests PASS.
-- WARNING: This script removes client privileges. Deployment is a separately approved step.
-- Run atomically with a fresh pre-migration ACL/policy snapshot and tested rollback plan.
BEGIN;
DO $guard$
DECLARE
    v_explicit_operator_approval boolean := false;  -- must be changed only after recorded owner approval
BEGIN
    IF v_explicit_operator_approval IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Approval Center cutover requires an explicit, separately recorded production authorization';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.jarvis_approval_admin a
                   JOIN public.principal p ON p.id = a.principal_id AND p.tenant_id = a.tenant_id
                   WHERE a.enabled = true AND a.granted_at IS NOT NULL)
    THEN
        RAISE EXCEPTION 'No independently verified Approval Center administrator enrolled';
    END IF;
    IF pg_catalog.to_regprocedure('public.jarvis_approval_decide(uuid,uuid,text,text)') IS NULL
       OR pg_catalog.to_regprocedure('public.jarvis_approval_open(uuid,uuid,text,text,text,text,text,numeric)') IS NULL
       OR pg_catalog.to_regprocedure('public.jarvis_approval_check(uuid,uuid,text)') IS NULL
    THEN
        RAISE EXCEPTION 'Backend approval RPCs are missing';
    END IF;
END $guard$;

REVOKE SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.approval_decision, public.approval_request, public.approval_audit_log
  FROM anon, authenticated, PUBLIC;

DROP POLICY IF EXISTS jarvis_anon_tenant_insert ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_anon_tenant_select ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_anon_tenant_update ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_backend_insert_pending ON public.approval_decision;
DROP POLICY IF EXISTS jarvis_backend_insert_request ON public.approval_request;
DROP POLICY IF EXISTS jarvis_backend_insert_audit ON public.approval_audit_log;

-- Separate review: public.jarvis_memory has anonymous INSERT and
-- public/all-role NULL-owner policies. Memory migration must be coordinated
-- with other consumers of the shared database; no blanket privileges altered here.
COMMIT;
