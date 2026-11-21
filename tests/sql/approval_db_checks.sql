-- Real transaction tests with synthetic identities, no production access.
\set ON_ERROR_STOP on

-- The staging script should not auto-enroll any human.
DO $test$
BEGIN
    IF EXISTS (SELECT 1 FROM public.jarvis_approval_admin) THEN
        RAISE EXCEPTION 'unexpected enrollment';
    END IF;
    IF has_function_privilege('anon',
        'public.jarvis_approval_open(uuid,uuid,text,text,text,text,text,numeric)',
        'EXECUTE') THEN RAISE EXCEPTION 'anon can open approvals'; END IF;
    IF has_function_privilege('authenticated',
        'public.jarvis_approval_decide(uuid,uuid,text,text)', 'EXECUTE')
    THEN RAISE EXCEPTION 'authenticated can decide approvals'; END IF;
    IF has_function_privilege('anon',
        'public.jarvis_approval_check(uuid,uuid,text)', 'EXECUTE')
    THEN RAISE EXCEPTION 'anon can bypass action readback'; END IF;
END $test$;

-- One known synthetic verified owner only (test fixture).
INSERT INTO public.jarvis_approval_admin
    (auth_user_id, tenant_id, principal_id, enabled, granted_at)
VALUES ('12345678-1234-4234-8234-123456789abc',
        '00000000-0000-0000-0000-000000000001',
        '11111111-1111-1111-1111-111111111111',true,now());

DO $test$
DECLARE
    v_open jsonb;
    v_decide jsonb;
    v_req uuid;
    v_dec uuid;
    v_digest text := repeat('a',64);
    v_tenant uuid := '00000000-0000-0000-0000-000000000001'::uuid;
    v_user uuid := '12345678-1234-4234-8234-123456789abc'::uuid;
BEGIN
    v_open := public.jarvis_approval_open(
        v_tenant, '22222222-2222-2222-2222-222222222222'::uuid,
        'Synthetic request', 'Synthetic action only', 'R2',
        v_digest, 'synthetic-run-001', 0.10
    );
    IF v_open->>'status' <> 'pending_approval' THEN
        RAISE EXCEPTION 'open state incorrect';
    END IF;
    v_req := (v_open->>'request_id')::uuid;
    IF public.jarvis_approval_check(v_tenant, v_req, v_digest) THEN
        RAISE EXCEPTION 'unapproved action passed verifier';
    END IF;

    v_decide := public.jarvis_approval_decide(v_user,v_req,'approved','CI approval');
    IF v_decide->>'response' <> 'approved' THEN
        RAISE EXCEPTION 'owner approval did not persist';
    END IF;
    v_dec := (v_decide->>'decision_id')::uuid;
    IF NOT public.jarvis_approval_check(v_tenant,v_req,v_digest) THEN
        RAISE EXCEPTION 'approved action fails readback';
    END IF;
    IF public.jarvis_approval_check(v_tenant,v_req,repeat('b',64)) THEN
        RAISE EXCEPTION 'wrong action hash bypassed check';
    END IF;
    IF public.jarvis_approval_check('00000000-0000-0000-0000-000000000002'::uuid,
                                    v_req,v_digest) THEN
        RAISE EXCEPTION 'cross tenant approval passed';
    END IF;
    IF (SELECT count(*) FROM public.approval_audit_log WHERE request_id=v_req) <> 2 THEN
        RAISE EXCEPTION 'missing atomic audit trail';
    END IF;
    IF (SELECT status FROM public.approval_decision WHERE id=v_dec) <> 'approved' THEN
        RAISE EXCEPTION 'decision not marked approved';
    END IF;

    BEGIN
        PERFORM public.jarvis_approval_decide(v_user,v_req,'rejected',null);
        RAISE EXCEPTION 'double decision unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE 'P0001' THEN NULL;
    END;

    UPDATE public.approval_request SET expires_at=now()-interval '1 second' WHERE id=v_req;
    IF public.jarvis_approval_check(v_tenant,v_req,v_digest) THEN
        RAISE EXCEPTION 'expired approval remained usable';
    END IF;

    v_open := public.jarvis_approval_open(
        v_tenant, '22222222-2222-2222-2222-222222222222'::uuid,
        'Second request', 'For isolation', 'R3', repeat('c',64),
        'synthetic-run-002',0
    );
    v_req := (v_open->>'request_id')::uuid;
    BEGIN
        PERFORM public.jarvis_approval_decide(
            'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid,
            v_req, 'approved', null
        );
        RAISE EXCEPTION 'unknown owner unexpectedly approved';
    EXCEPTION WHEN SQLSTATE '42501' THEN NULL;
    END;
    IF public.jarvis_approval_check(v_tenant,v_req,repeat('c',64)) THEN
        RAISE EXCEPTION 'unapproved request passed';
    END IF;
END $test$;

-- SQL privileges, not only RLS, prevent anon/auth from executing RPCs.
DO $test$
BEGIN
    IF has_function_privilege('anon',
        'public.jarvis_approval_check(uuid,uuid,text)','EXECUTE') THEN
        RAISE EXCEPTION 'anon function EXECUTE grant';
    END IF;
    IF has_table_privilege('anon','public.jarvis_approval_admin','SELECT') THEN
        RAISE EXCEPTION 'anon can read admin mapping';
    END IF;
END $test$;
