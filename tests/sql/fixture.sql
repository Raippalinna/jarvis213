-- Minimal local contract fixture, NOT a production schema/migration.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.principal (
  id uuid PRIMARY KEY, tenant_id uuid NOT NULL,
  type text NOT NULL CHECK (type IN ('human','system','agent'))
);
CREATE TABLE public.system_config (key text, value text);
CREATE TABLE public.approval_decision (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL, title text NOT NULL, description text,
  decision_type text NOT NULL CHECK (decision_type IN ('investment','contract','hire','offer','policy','other')),
  status text NOT NULL CHECK (status IN ('draft','pending_approval','approved','rejected','cancelled','executed')),
  risk_class text NOT NULL CHECK (risk_class IN ('R0','R1','R2','R3')),
  probability numeric DEFAULT 0.5, cash_required numeric,
  reversibility text CHECK (reversibility IN ('reversible','partially_reversible','irreversible')),
  owner_principal_id uuid REFERENCES public.principal(id), expires_at timestamptz
);
CREATE TABLE public.approval_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id uuid NOT NULL REFERENCES public.approval_decision(id),
  request_type text NOT NULL CHECK (request_type IN ('create','update','execute','cancel')),
  risk_class text NOT NULL, requested_by uuid NOT NULL REFERENCES public.principal(id),
  auto_approved boolean DEFAULT false, response text, expires_at timestamptz
);
CREATE TABLE public.approval_audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL, event_type text NOT NULL,
  actor_principal_id uuid REFERENCES public.principal(id),
  actor_type text NOT NULL CHECK (actor_type IN ('human','system','agent')),
  decision_id uuid REFERENCES public.approval_decision(id),
  request_id uuid REFERENCES public.approval_request(id), metadata jsonb
);
ALTER TABLE public.approval_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approval_audit_log ENABLE ROW LEVEL SECURITY;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT ON public.principal TO service_role;
GRANT SELECT, UPDATE ON public.system_config TO service_role;
GRANT SELECT, INSERT ON public.approval_decision, public.approval_request,
  public.approval_audit_log TO service_role;
-- SELECT FOR SHARE additionally requires UPDATE; production prerequisite,
-- not a grant applied by the candidate migration.
GRANT UPDATE ON public.approval_decision, public.approval_request TO service_role;
INSERT INTO public.principal VALUES
  ('22222222-2222-4222-8222-222222222222',
   '11111111-1111-4111-8111-111111111111', 'agent');
INSERT INTO public.system_config VALUES ('autonomy_enabled', 'true');
