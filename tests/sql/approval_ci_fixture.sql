-- Ephemeral PostgreSQL 17 fixture. Synthetic data only. Never production.
CREATE SCHEMA IF NOT EXISTS auth;
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role BYPASSRLS; END IF;
END $roles$;
CREATE TABLE auth.users (
    id uuid PRIMARY KEY,
    email_confirmed_at timestamptz
);
CREATE TABLE public.tenant (id uuid PRIMARY KEY);
CREATE TABLE public.principal (
    id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES public.tenant(id),
    type text NOT NULL
);
CREATE TABLE public.approval_decision (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES public.tenant(id),
    title text NOT NULL, description text,
    decision_type text NOT NULL, status text NOT NULL DEFAULT 'draft',
    risk_class text NOT NULL, reversibility text NOT NULL DEFAULT 'reversible',
    owner_principal_id uuid REFERENCES public.principal(id),
    approver_principal_id uuid REFERENCES public.principal(id),
    cash_required numeric, draft_ref text, expires_at timestamptz,
    approved_at timestamptz, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.approval_request (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id uuid NOT NULL REFERENCES public.approval_decision(id),
    request_type text NOT NULL, risk_class text NOT NULL,
    requested_by uuid NOT NULL REFERENCES public.principal(id),
    requested_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz, auto_approved boolean DEFAULT false,
    response text, reviewed_by uuid REFERENCES public.principal(id),
    reviewed_at timestamptz, response_reason text
);
CREATE TABLE public.approval_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES public.tenant(id),
    event_type text NOT NULL, actor_principal_id uuid REFERENCES public.principal(id),
    actor_type text NOT NULL, decision_id uuid REFERENCES public.approval_decision(id),
    request_id uuid REFERENCES public.approval_request(id),
    metadata jsonb DEFAULT '{}'::jsonb, occurred_at timestamptz NOT NULL DEFAULT now()
);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE
 ON public.approval_decision, public.approval_request, public.approval_audit_log
 TO anon, authenticated, service_role;
ALTER TABLE public.approval_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY jarvis_anon_tenant_insert ON public.approval_decision
 FOR INSERT TO anon WITH CHECK (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE POLICY jarvis_anon_tenant_select ON public.approval_decision
 FOR SELECT TO anon USING (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE POLICY jarvis_anon_tenant_update ON public.approval_decision
 FOR UPDATE TO anon USING (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid)
 WITH CHECK (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE POLICY jarvis_backend_insert_pending ON public.approval_decision
 FOR INSERT TO anon, authenticated WITH CHECK (status IN ('draft','pending_approval'));
CREATE POLICY jarvis_backend_insert_request ON public.approval_request
 FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY jarvis_backend_insert_audit ON public.approval_audit_log
 FOR INSERT TO anon, authenticated WITH CHECK (true);

INSERT INTO public.tenant (id) VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO public.principal (id,tenant_id,type) VALUES
 ('11111111-1111-1111-1111-111111111111','00000000-0000-0000-0000-000000000001','human'),
 ('22222222-2222-2222-2222-222222222222','00000000-0000-0000-0000-000000000001','agent');
INSERT INTO auth.users (id,email_confirmed_at)
 VALUES ('12345678-1234-4234-8234-123456789abc',now());
