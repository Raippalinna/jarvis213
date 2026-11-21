-- CANDIDATE ONLY. Explicit approval and the separate RLS hardening are required
-- before production use. This function creates review requests, never authority.
BEGIN;
CREATE TABLE public.jarvis_review_receipt_v1 (
  request_key text PRIMARY KEY CHECK (request_key ~ '^[0-9a-f]{64}$'),
  decision_id uuid NOT NULL UNIQUE REFERENCES public.approval_decision(id),
  request_id uuid NOT NULL UNIQUE REFERENCES public.approval_request(id),
  audit_id uuid NOT NULL UNIQUE REFERENCES public.approval_audit_log(id)
);
ALTER TABLE public.jarvis_review_receipt_v1 ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.jarvis_review_receipt_v1 FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.jarvis_review_receipt_v1 TO service_role;
CREATE POLICY jarvis_review_server ON public.jarvis_review_receipt_v1
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE FUNCTION public.jarvis_open_review_v1(
  p_tenant uuid, p_actor uuid, p_session text, p_task text,
  p_risk text, p_reason text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog
AS $$
DECLARE
  v_key text;
  v_switch text;
  v_receipt public.jarvis_review_receipt_v1%ROWTYPE;
  v_decision public.approval_decision%ROWTYPE;
  v_request public.approval_request%ROWTYPE;
  v_expires timestamptz;
BEGIN
  IF current_user <> 'service_role' THEN
    RAISE EXCEPTION 'trusted_server_role_required' USING ERRCODE = '42501';
  END IF;
  IF p_tenant IS NULL OR p_actor IS NULL
     OR p_risk IS NULL OR p_risk NOT IN ('R2', 'R3')
     OR p_session IS NULL OR length(btrim(p_session)) NOT BETWEEN 1 AND 128
     OR p_task IS NULL OR length(btrim(p_task)) NOT BETWEEN 1 AND 2000
     OR p_reason IS NULL OR length(btrim(p_reason)) NOT BETWEEN 1 AND 300 THEN
    RAISE EXCEPTION 'invalid_review_input' USING ERRCODE = '22023';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.principal
    WHERE id = p_actor AND tenant_id = p_tenant AND type = 'agent'
  ) THEN
    RAISE EXCEPTION 'actor_tenant_mismatch' USING ERRCODE = '42501';
  END IF;

  -- One exact TEXT true value is required. STRICT rejects missing/duplicate rows.
  -- FOR SHARE keeps the observed flag stable until this transaction completes.
  SELECT value INTO STRICT v_switch FROM public.system_config
    WHERE key = 'autonomy_enabled' FOR SHARE;
  IF v_switch IS DISTINCT FROM 'true' THEN
    RAISE EXCEPTION 'autonomy_disabled' USING ERRCODE = '42501';
  END IF;

  v_key := encode(sha256(convert_to(
    jsonb_build_array('review-v1', p_tenant, p_actor, p_session,
                     p_task, p_risk, p_reason)::text, 'UTF8')), 'hex');
  -- A hash collision only serializes unrelated transactions; the full 256-bit
  -- key and the unique constraint decide identity.
  PERFORM pg_advisory_xact_lock(hashtextextended(v_key, 0));
  SELECT * INTO v_receipt FROM public.jarvis_review_receipt_v1
    WHERE request_key = v_key;
  IF FOUND THEN
    SELECT * INTO STRICT v_decision FROM public.approval_decision
      WHERE id = v_receipt.decision_id FOR SHARE;
    SELECT * INTO STRICT v_request FROM public.approval_request
      WHERE id = v_receipt.request_id FOR SHARE;
    IF v_decision.tenant_id IS DISTINCT FROM p_tenant
       OR v_decision.owner_principal_id IS DISTINCT FROM p_actor
       OR v_decision.status IS DISTINCT FROM 'pending_approval'
       OR v_decision.description IS DISTINCT FROM p_task
       OR v_decision.risk_class IS DISTINCT FROM p_risk
       OR v_decision.expires_at IS NULL OR v_decision.expires_at <= now()
       OR v_request.decision_id IS DISTINCT FROM v_decision.id
       OR v_request.requested_by IS DISTINCT FROM p_actor
       OR v_request.request_type IS DISTINCT FROM 'create'
       OR v_request.risk_class IS DISTINCT FROM p_risk
       OR v_request.response IS NOT NULL
       OR v_request.auto_approved IS DISTINCT FROM false
       OR v_request.expires_at IS NULL OR v_request.expires_at <= now() THEN
      RAISE EXCEPTION 'review_no_longer_pending' USING ERRCODE = '22023';
    END IF;
    v_expires := least(v_decision.expires_at, v_request.expires_at);
  ELSE
    v_expires := now() + interval '24 hours';
    INSERT INTO public.approval_decision (
      tenant_id, title, description, decision_type, status, risk_class,
      probability, cash_required, reversibility, owner_principal_id, expires_at
    ) VALUES (
      p_tenant, left(p_task, 120), p_task, 'other', 'pending_approval', p_risk,
      NULL, NULL, NULL, p_actor, v_expires
    ) RETURNING id INTO v_receipt.decision_id;
    INSERT INTO public.approval_request (
      decision_id, request_type, risk_class, requested_by, auto_approved, expires_at
    ) VALUES (
      v_receipt.decision_id, 'create', p_risk, p_actor, false, v_expires
    ) RETURNING id INTO v_receipt.request_id;
    INSERT INTO public.approval_audit_log (
      tenant_id, event_type, actor_principal_id, actor_type,
      decision_id, request_id, metadata
    ) VALUES (
      p_tenant, 'gate_opened', p_actor, 'agent',
      v_receipt.decision_id, v_receipt.request_id,
      jsonb_build_object('session_id', p_session, 'risk_class', p_risk,
        'reason', p_reason, 'execution_authorized', false, 'request_scope', 'review_only')
    ) RETURNING id INTO v_receipt.audit_id;
    INSERT INTO public.jarvis_review_receipt_v1
      VALUES (v_key, v_receipt.decision_id, v_receipt.request_id, v_receipt.audit_id);
  END IF;
  RETURN jsonb_build_object(
    'decision_id', v_receipt.decision_id, 'request_id', v_receipt.request_id,
    'audit_id', v_receipt.audit_id, 'state', 'pending_approval',
    'scope', 'review_only', 'execution_authorized', false, 'expires_at', v_expires);
END
$$;
REVOKE ALL ON FUNCTION public.jarvis_open_review_v1(uuid,uuid,text,text,text,text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.jarvis_open_review_v1(uuid,uuid,text,text,text,text)
  TO service_role;
COMMIT;
