-- MANUAL OWNER ENROLLMENT. Run ONLY after independent identity verification.
-- Stage 01 must be applied first. No user is auto-enrolled.
-- Replace NULL::uuid below with the specific SUPABASE AUTH USER ID you have
-- verified as the intended human owner. Never derive identity from the first
-- person to sign up or from a user-controlled email claim.
BEGIN;
DO $enroll$
DECLARE
    v_verified_user_id uuid := NULL::uuid;
    v_tenant uuid := '00000000-0000-0000-0000-000000000001'::uuid;
    v_human uuid := '11111111-1111-1111-1111-111111111111'::uuid;
BEGIN
    IF v_verified_user_id IS NULL THEN
        RAISE EXCEPTION 'Owner Auth UID must be explicitly set after independent verification';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM auth.users u
                   WHERE u.id = v_verified_user_id AND u.email_confirmed_at IS NOT NULL)
       OR NOT EXISTS (SELECT 1 FROM public.principal p
                      WHERE p.id = v_human AND p.tenant_id = v_tenant AND p.type = 'human')
    THEN
        RAISE EXCEPTION 'No verified owner Auth user / human principal mapping';
    END IF;
    INSERT INTO public.jarvis_approval_admin
        (auth_user_id, tenant_id, principal_id, enabled, granted_at)
    VALUES (v_verified_user_id, v_tenant, v_human, true, now())
    ON CONFLICT (auth_user_id) DO NOTHING;
END $enroll$;
COMMIT;
