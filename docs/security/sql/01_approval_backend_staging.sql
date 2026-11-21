-- STAGING ONLY. REVIEW + explicit approval required before applying to Supabase.
-- Additive stage: zero enrolled admins, no changes to existing grants or RLS.
-- Run in a transaction as postgres. Production cutover is a separate reviewed file.
BEGIN;

CREATE TABLE IF NOT EXISTS public.jarvis_approval_admin (
    auth_user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL REFERENCES public.tenant(id),
    principal_id uuid NOT NULL REFERENCES public.principal(id),
    enabled boolean NOT NULL DEFAULT false,
    granted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT jarvis_approval_admin_enabled_check CHECK (NOT enabled OR granted_at IS NOT NULL)
);
ALTER TABLE public.jarvis_approval_admin ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.jarvis_approval_admin FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE public.jarvis_approval_admin TO service_role;

-- One transaction or no changes at all. Backend must have a verified service role.
-- Neither a client nor an LLM may call this without server privileges.
CREATE OR REPLACE FUNCTION public.jarvis_approval_open(
    p_tenant_id uuid, p_agent_principal_id uuid, p_title text,
    p_description text, p_risk text, p_action_sha256 text,
    p_session_id text, p_est_cost numeric DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $fn$
DECLARE
    v_decision uuid;
    v_request uuid;
    v_expires timestamptz := now() + interval '24 hours';
BEGIN
    IF p_tenant_id IS NULL OR p_agent_principal_id IS NULL
       OR p_risk NOT IN ('R2','R3')
       OR p_title IS NULL OR length(btrim(p_title)) NOT BETWEEN 4 AND 120
       OR p_description IS NULL OR length(p_description) NOT BETWEEN 1 AND 2000
       OR p_action_sha256 IS NULL OR p_action_sha256 !~ '^[0-9a-f]{64}$'
       OR p_session_id IS NULL OR length(p_session_id) NOT BETWEEN 1 AND 128
       OR (p_est_cost IS NOT NULL AND (p_est_cost < 0 OR p_est_cost > 200))
    THEN
        RAISE EXCEPTION 'invalid_approval_open' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.principal p
        WHERE p.id = p_agent_principal_id AND p.tenant_id = p_tenant_id
          AND p.type = 'agent'
    ) THEN
        RAISE EXCEPTION 'invalid_agent_scope' USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.approval_decision (
        tenant_id, title, description, decision_type, status, risk_class,
        reversibility, owner_principal_id, cash_required, draft_ref, expires_at
    ) VALUES (
        p_tenant_id, p_title, p_description,
        CASE WHEN p_risk = 'R3' THEN 'contract' ELSE 'other' END,
        'pending_approval', p_risk,
        CASE WHEN p_risk = 'R3' THEN 'irreversible' ELSE 'reversible' END,
        p_agent_principal_id, NULLIF(p_est_cost, 0),
        'sha256:' || p_action_sha256, v_expires
    ) RETURNING id INTO v_decision;

    INSERT INTO public.approval_request (
        decision_id, request_type, risk_class, requested_by, expires_at, auto_approved
    ) VALUES (
        v_decision, 'execute', p_risk, p_agent_principal_id, v_expires, false
    ) RETURNING id INTO v_request;

    INSERT INTO public.approval_audit_log (
        tenant_id, event_type, actor_principal_id, actor_type,
        decision_id, request_id, metadata
    ) VALUES (
        p_tenant_id, 'gate_opened', p_agent_principal_id, 'agent',
        v_decision, v_request,
        pg_catalog.jsonb_build_object(
            'session_id', p_session_id, 'action_sha256', p_action_sha256,
            'risk_class', p_risk
        )
    );
    RETURN pg_catalog.jsonb_build_object(
        'request_id', v_request::text, 'status', 'pending_approval'
    );
END
$fn$;

-- Only the verified owner, through a backend-authenticated Edge Function,
-- may approve a bound, unexpired R2/R3 request belonging to their tenant.
CREATE OR REPLACE FUNCTION public.jarvis_approval_decide(
    p_auth_user_id uuid, p_request_id uuid, p_response text,
    p_reason text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $fn$
DECLARE
    v_tenant uuid;
    v_principal uuid;
    v_decision uuid;
    v_hash text;
BEGIN
    IF p_auth_user_id IS NULL OR p_request_id IS NULL
       OR p_response IS NULL OR p_response NOT IN ('approved', 'rejected')
       OR (p_reason IS NOT NULL AND length(p_reason) > 500)
    THEN
        RAISE EXCEPTION 'invalid_approval_decision' USING ERRCODE = '22023';
    END IF;

    SELECT a.tenant_id, a.principal_id INTO v_tenant, v_principal
      FROM public.jarvis_approval_admin a
      JOIN public.principal p ON p.id = a.principal_id AND p.tenant_id = a.tenant_id
     WHERE a.auth_user_id = p_auth_user_id AND a.enabled = true
     FOR SHARE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_authorized' USING ERRCODE = '42501';
    END IF;

    SELECT r.decision_id, d.draft_ref INTO v_decision, v_hash
      FROM public.approval_request r
      JOIN public.approval_decision d ON d.id = r.decision_id
     WHERE r.id = p_request_id AND d.tenant_id = v_tenant
       AND r.response IS NULL AND r.request_type = 'execute'
       AND r.auto_approved IS DISTINCT FROM true
       AND r.expires_at IS NOT NULL AND r.expires_at > now()
       AND d.expires_at IS NOT NULL AND d.expires_at > now()
       AND d.status = 'pending_approval' AND d.risk_class = r.risk_class
       AND d.risk_class IN ('R2','R3')
       AND d.draft_ref ~ '^sha256:[0-9a-f]{64}$'
     FOR UPDATE OF r, d;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_pending_or_not_authorized' USING ERRCODE = 'P0001';
    END IF;

    UPDATE public.approval_request
       SET response = p_response, reviewed_by = v_principal,
           reviewed_at = now(), response_reason = p_reason
     WHERE id = p_request_id AND response IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'concurrent_approval' USING ERRCODE = 'P0001';
    END IF;
    UPDATE public.approval_decision
       SET status = CASE WHEN p_response = 'approved' THEN 'approved' ELSE 'rejected' END,
           approver_principal_id = v_principal,
           approved_at = CASE WHEN p_response = 'approved' THEN now() ELSE NULL END,
           updated_at = now()
     WHERE id = v_decision AND status = 'pending_approval';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'concurrent_decision' USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO public.approval_audit_log (
        tenant_id, event_type, actor_principal_id, actor_type,
        decision_id, request_id, metadata
    ) VALUES (
        v_tenant,
        CASE WHEN p_response = 'approved' THEN 'decision_approved' ELSE 'decision_rejected' END,
        v_principal, 'human', v_decision, p_request_id,
        pg_catalog.jsonb_build_object('action_ref', v_hash)
    );
    RETURN pg_catalog.jsonb_build_object(
        'request_id', p_request_id::text, 'decision_id', v_decision::text,
        'response', p_response
    );
END
$fn$;

-- Executor-side proof: only the exact approved, still-unexpired action may run.
-- No client-provided approval ID or tenant alone counts as authorization.
CREATE OR REPLACE FUNCTION public.jarvis_approval_check(
    p_tenant_id uuid, p_request_id uuid, p_action_sha256 text
) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $fn$
    SELECT COALESCE(
        p_tenant_id IS NOT NULL
        AND p_request_id IS NOT NULL
        AND p_action_sha256 ~ '^[0-9a-f]{64}$'
        AND EXISTS (
            SELECT 1
              FROM public.approval_request r
              JOIN public.approval_decision d ON d.id = r.decision_id
             WHERE r.id = p_request_id AND d.tenant_id = p_tenant_id
               AND r.request_type = 'execute' AND r.response = 'approved'
               AND r.auto_approved IS DISTINCT FROM true
               AND r.expires_at IS NOT NULL AND r.expires_at > now()
               AND d.expires_at IS NOT NULL AND d.expires_at > now()
               AND d.status = 'approved'
               AND d.risk_class = r.risk_class AND d.risk_class IN ('R2','R3')
               AND d.draft_ref = ('sha256:' || p_action_sha256)
        ), false
    );
$fn$;

REVOKE ALL ON FUNCTION public.jarvis_approval_open(uuid,uuid,text,text,text,text,text,numeric) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.jarvis_approval_decide(uuid,uuid,text,text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.jarvis_approval_check(uuid,uuid,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.jarvis_approval_open(uuid,uuid,text,text,text,text,text,numeric) TO service_role;
GRANT EXECUTE ON FUNCTION public.jarvis_approval_decide(uuid,uuid,text,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.jarvis_approval_check(uuid,uuid,text) TO service_role;

COMMIT;
