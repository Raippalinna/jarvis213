-- Historical policy snapshot for incident recovery ONLY.
-- DANGEROUS: restores the original anonymous access weakness.
-- Never execute automatically to make a UI or test pass.
BEGIN;
CREATE POLICY jarvis_anon_tenant_insert ON public.approval_decision
  FOR INSERT TO anon
  WITH CHECK (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE POLICY jarvis_anon_tenant_select ON public.approval_decision
  FOR SELECT TO anon
  USING (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE POLICY jarvis_anon_tenant_update ON public.approval_decision
  FOR UPDATE TO anon
  USING (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid)
  WITH CHECK (tenant_id = '00000000-0000-0000-0000-000000000001'::uuid);
CREATE POLICY jarvis_backend_insert_pending ON public.approval_decision
  FOR INSERT TO anon, authenticated
  WITH CHECK (status = ANY (ARRAY['draft'::text, 'pending_approval'::text]));
CREATE POLICY jarvis_backend_insert_request ON public.approval_request
  FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY jarvis_backend_insert_audit ON public.approval_audit_log
  FOR INSERT TO anon, authenticated WITH CHECK (true);
COMMIT;
