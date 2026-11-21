-- JARVIS KPI snapshot: move scheduled privileged writes out of a public Edge Function.
-- This migration is prepared for review only. It is NOT applied to production by this PR.

CREATE OR REPLACE FUNCTION public.jarvis_kpi_snapshot()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
  v_tenant CONSTANT uuid := '00000000-0000-0000-0000-000000000001'::uuid;
  v_now timestamptz := clock_timestamp();
  v_bucket timestamptz;
  v_day_start timestamptz;
  v_day text;
  v_idempotency_key text;
  v_existing_episode uuid;
  v_existing_event uuid;
  v_episode_id uuid;
  v_event_id uuid;
  v_events_today bigint;
  v_active_entities bigint;
  v_open_approvals bigint;
  v_pending_dead_letters bigint := NULL;
  v_dead_letters_scope text := 'not_tenant_scoped';
  v_summary text;
BEGIN
  -- Stable two-hour bucket: duplicate/manual/concurrent invocations collapse to one snapshot.
  v_bucket := to_timestamp(floor(extract(epoch FROM v_now) / 7200) * 7200);
  v_day_start := date_trunc('day', v_now AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
  v_day := to_char(v_day_start AT TIME ZONE 'UTC', 'YYYY-MM-DD');
  v_idempotency_key := 'kpi:' || v_tenant::text || ':' ||
    to_char(v_bucket AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"');

  PERFORM pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(v_idempotency_key, 0)
  );

  -- Reuse any snapshot created by the former Edge Function in this same bucket.
  SELECT me.id
    INTO v_existing_episode
    FROM public.memory_episode AS me
   WHERE me.tenant_id = v_tenant
     AND me.episode_type = 'kpi_snapshot'
     AND me.started_at >= v_bucket
     AND me.started_at < v_bucket + interval '2 hours'
     AND me.source_systems @> ARRAY['jarvis-kpi-snapshot']::text[]
   ORDER BY me.created_at
   LIMIT 1;

  SELECT e.event_id
    INTO v_existing_event
    FROM public.event AS e
   WHERE e.tenant_id = v_tenant
     AND e.source = 'jarvis-kpi-snapshot'
     AND e.event_type = 'kpi.snapshot.periodic'
     AND e.occurred_at >= v_bucket
     AND e.occurred_at < v_bucket + interval '2 hours'
   ORDER BY e.occurred_at
   LIMIT 1;

  IF v_existing_episode IS NOT NULL AND v_existing_event IS NOT NULL THEN
    RETURN jsonb_build_object(
      'ok', true,
      'duplicate', true,
      'snapshot_bucket', v_bucket,
      'episode_id', v_existing_episode,
      'event_id', v_existing_event
    );
  END IF;

  SELECT count(*) INTO v_events_today
    FROM public.event
   WHERE tenant_id = v_tenant
     AND occurred_at >= v_day_start
     AND occurred_at < v_day_start + interval '1 day';

  SELECT count(*) INTO v_active_entities
    FROM public.entity
   WHERE tenant_id = v_tenant;

  SELECT count(*) INTO v_open_approvals
    FROM public.approval_decision
   WHERE tenant_id = v_tenant
     AND status IN ('draft', 'pending');

  -- Current production schema has no tenant_id on dead_letter. Never count
  -- unscoped rows into a tenant-specific snapshot; report unknown until scoped.
  IF EXISTS (
    SELECT 1
      FROM pg_catalog.pg_attribute
     WHERE attrelid = 'public.dead_letter'::regclass
       AND attname = 'tenant_id'
       AND NOT attisdropped
  ) THEN
    EXECUTE 'SELECT count(*) FROM public.dead_letter WHERE tenant_id = $1'
      INTO v_pending_dead_letters
      USING v_tenant;
    v_dead_letters_scope := 'tenant_scoped';
  ELSE
    v_pending_dead_letters := NULL;
    v_dead_letters_scope := 'not_tenant_scoped';
  END IF;

  v_summary := 'KPI ' || v_day || ': ' ||
    v_events_today::text || ' events, ' ||
    v_active_entities::text || ' entities, ' ||
    v_open_approvals::text || ' pending approvals, ' ||
    CASE
      WHEN v_pending_dead_letters IS NULL THEN 'dead letters: not tenant-scoped'
      ELSE v_pending_dead_letters::text || ' dead letters'
    END;

  IF v_existing_episode IS NULL THEN
    INSERT INTO public.memory_episode (
      tenant_id, episode_type, title, summary, started_at, ended_at, source_systems
    ) VALUES (
      v_tenant,
      'kpi_snapshot',
      'Daily KPI Snapshot ' || v_day,
      v_summary,
      v_bucket,
      v_now,
      ARRAY['supabase', 'jarvis-kpi-snapshot']::text[]
    )
    RETURNING id INTO v_episode_id;
  ELSE
    v_episode_id := v_existing_episode;
  END IF;

  IF v_existing_event IS NULL THEN
    INSERT INTO public.event (
      tenant_id, event_type, occurred_at, source, idempotency_key, classification
    ) VALUES (
      v_tenant,
      'kpi.snapshot.periodic',
      v_now,
      'jarvis-kpi-snapshot',
      v_idempotency_key,
      'trusted'
    )
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING event_id INTO v_event_id;

    IF v_event_id IS NULL THEN
      SELECT e.event_id
        INTO v_event_id
        FROM public.event AS e
       WHERE e.idempotency_key = v_idempotency_key
       LIMIT 1;
    END IF;
  ELSE
    v_event_id := v_existing_event;
  END IF;

  RETURN jsonb_build_object(
    'ok', true,
    'duplicate', false,
    'snapshot_bucket', v_bucket,
    'episode_id', v_episode_id,
    'event_id', v_event_id,
    'kpis', jsonb_build_object(
      'events_today', v_events_today,
      'active_entities', v_active_entities,
      'open_approvals', v_open_approvals,
      'dead_letters', v_pending_dead_letters,
      'dead_letters_scope', v_dead_letters_scope
    ),
    'summary', v_summary
  );
END;
$function$;

-- The function is owned by postgres and callable only by the postgres cron role.
ALTER FUNCTION public.jarvis_kpi_snapshot() OWNER TO postgres;
REVOKE ALL ON FUNCTION public.jarvis_kpi_snapshot() FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.jarvis_kpi_snapshot() TO postgres;

COMMENT ON FUNCTION public.jarvis_kpi_snapshot() IS
  'Private idempotent two-hour KPI snapshot. Execute only through the postgres-owned pg_cron job.';

-- Replace the old unauthenticated HTTP call with an in-database invocation.
DO $migration$
DECLARE
  v_job_id bigint;
BEGIN
  FOR v_job_id IN
    SELECT jobid FROM cron.job WHERE jobname = 'jarvis-kpi-snapshot'
  LOOP
    PERFORM cron.unschedule(v_job_id);
  END LOOP;

  PERFORM cron.schedule(
    'jarvis-kpi-snapshot',
    '0 */2 * * *',
    'SELECT public.jarvis_kpi_snapshot();'
  );

  IF NOT EXISTS (
    SELECT 1
      FROM cron.job
     WHERE jobname = 'jarvis-kpi-snapshot'
       AND schedule = '0 */2 * * *'
       AND active = true
       AND username = 'postgres'
       AND command = 'SELECT public.jarvis_kpi_snapshot();'
  ) THEN
    RAISE EXCEPTION 'jarvis-kpi-snapshot cron job did not install with the expected postgres-owned command';
  END IF;
END;
$migration$;
