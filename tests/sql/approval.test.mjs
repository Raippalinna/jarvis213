import { PGlite } from '@electric-sql/pglite';
import assert from 'node:assert/strict';
import { before, after, beforeEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';

const tenant = '11111111-1111-4111-8111-111111111111';
const actor = '22222222-2222-4222-8222-222222222222';
const sql = `SELECT public.jarvis_open_review_v1($1::uuid,$2::uuid,$3,$4,$5,$6) AS receipt`;
const base = [tenant, actor, 'offline-1', 'TEST: granska utkast', 'R3', 'syntetiskt test'];
let db;
before(async () => {
  db = new PGlite();
  await db.exec(await readFile(new URL('./fixture.sql', import.meta.url), 'utf8'));
  await db.exec(await readFile(new URL('../../db/proposed/20260922_atomic_review.sql', import.meta.url), 'utf8'));
});
after(async () => db?.close());
beforeEach(async () => {
  await db.exec(`RESET ROLE;
    DROP TRIGGER IF EXISTS fail_audit ON public.approval_audit_log;
    DROP TRIGGER IF EXISTS fail_request ON public.approval_request;
    DROP TRIGGER IF EXISTS fail_receipt ON public.jarvis_review_receipt_v1;
    TRUNCATE public.jarvis_review_receipt_v1, public.approval_audit_log,
      public.approval_request, public.approval_decision;
    DELETE FROM public.system_config;
    INSERT INTO public.system_config VALUES ('autonomy_enabled','true');`);
});
async function open(args = base, role = 'service_role') {
  assert(['service_role', 'anon', 'authenticated'].includes(role));
  await db.exec(`SET ROLE ${role}`);
  try {
    return (await db.query(sql, args)).rows[0].receipt;
  } finally {
    await db.exec('RESET ROLE');
  }
}
async function counts() {
  return (await db.query(`SELECT
    (SELECT count(*)::int FROM public.approval_decision) AS decisions,
    (SELECT count(*)::int FROM public.approval_request) AS requests,
    (SELECT count(*)::int FROM public.approval_audit_log) AS audit,
    (SELECT count(*)::int FROM public.jarvis_review_receipt_v1) AS receipts`)).rows[0];
}
const empty = {decisions: 0, requests: 0, audit: 0, receipts: 0};

test('one transaction creates a review and audit, never execution authority', async () => {
  const r = await open();
  assert.equal(r.state, 'pending_approval');
  assert.equal(r.scope, 'review_only');
  assert.equal(r.execution_authorized, false);
  assert(Date.parse(r.expires_at) > Date.now());
  assert.deepEqual(await counts(), {decisions: 1, requests: 1, audit: 1, receipts: 1});
  const d = (await db.query('SELECT * FROM public.approval_decision')).rows[0];
  assert.equal(d.probability, null);
  assert.equal(d.cash_required, null);
  assert.equal(d.reversibility, null);
  const q = (await db.query('SELECT * FROM public.approval_request')).rows[0];
  assert.equal(q.request_type, 'create');
  assert.equal(q.auto_approved, false);
  const a = (await db.query('SELECT * FROM public.approval_audit_log')).rows[0];
  assert.equal(a.actor_type, 'agent');
  assert.equal(a.request_id, r.request_id);
});

test('identical retries return the same receipt without extending expiry', async () => {
  const first = await open();
  const retry = await open();
  assert.deepEqual(first, retry);
  assert.deepEqual(await counts(), {decisions: 1, requests: 1, audit: 1, receipts: 1});
});

test('changed content or session is a different review', async () => {
  const a = await open();
  const b = await open(base.map((v, i) => i === 3 ? v + ' ändrat' : v));
  const c = await open(base.map((v, i) => i === 2 ? 'offline-2' : v));
  assert.equal(new Set([a.request_id, b.request_id, c.request_id]).size, 3);
});

for (const [trigger, table] of [
  ['fail_request', 'approval_request'],
  ['fail_audit', 'approval_audit_log'],
  ['fail_receipt', 'jarvis_review_receipt_v1'],
]) {
  test(`failure writing ${table} rolls back ALL rows`, async () => {
    await db.exec(`CREATE OR REPLACE FUNCTION public.inject_failure() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected_failure'; END $$;
      CREATE TRIGGER ${trigger} BEFORE INSERT ON public.${table}
      FOR EACH ROW EXECUTE FUNCTION public.inject_failure();`);
    await assert.rejects(open(), /injected_failure/);
    assert.deepEqual(await counts(), empty);
  });
}

for (const role of ['anon', 'authenticated']) {
  test(`${role} cannot execute the RPC or read its receipt table`, async () => {
    await assert.rejects(open(base, role), /permission denied/);
    await db.exec(`SET ROLE ${role}`);
    try {
      await assert.rejects(db.query('SELECT * FROM public.jarvis_review_receipt_v1'), /permission denied/);
    } finally { await db.exec('RESET ROLE'); }
    assert.deepEqual(await counts(), empty);
  });
}

for (const value of ['false', 'TRUE', '', null]) {
  test(`kill switch ${JSON.stringify(value)} rejects all writes`, async () => {
    await db.query('UPDATE public.system_config SET value=$1', [value]);
    await assert.rejects(open(), /autonomy_disabled/);
    assert.deepEqual(await counts(), empty);
  });
}
test('missing or ambiguous kill switch rejects all writes', async () => {
  await db.exec('DELETE FROM public.system_config');
  await assert.rejects(open());
  await db.exec(`INSERT INTO public.system_config VALUES
    ('autonomy_enabled','true'), ('autonomy_enabled','true')`);
  await assert.rejects(open());
  assert.deepEqual(await counts(), empty);
});
test('wrong tenant cannot reuse the agent identity', async () => {
  const args = [...base];
  args[0] = '99999999-9999-4999-8999-999999999999';
  await assert.rejects(open(args), /actor_tenant_mismatch/);
  assert.deepEqual(await counts(), empty);
});
test('human identity cannot be presented as the requesting agent', async () => {
  await db.query("UPDATE public.principal SET type='human' WHERE id=$1", [actor]);
  try { await assert.rejects(open(), /actor_tenant_mismatch/); }
  finally { await db.query("UPDATE public.principal SET type='agent' WHERE id=$1", [actor]); }
  assert.deepEqual(await counts(), empty);
});
test('empty, excessive and invalid inputs are rejected', async () => {
  for (const [i, value] of [[2, ''], [3, ''], [3, 'x'.repeat(2001)], [4, 'R0'], [4, null], [5, '']]) {
    const args = [...base]; args[i] = value;
    await assert.rejects(open(args), /invalid_review_input/);
  }
  assert.deepEqual(await counts(), empty);
});
test('approved or expired requests cannot be revived through a retry', async () => {
  const first = await open();
  await db.query("UPDATE public.approval_decision SET status='approved' WHERE id=$1", [first.decision_id]);
  await assert.rejects(open(), /review_no_longer_pending/);
  await db.query("UPDATE public.approval_decision SET status='pending_approval', expires_at=now()-interval '1 minute'");
  await assert.rejects(open(), /review_no_longer_pending/);
  assert.deepEqual(await counts(), {decisions: 1, requests: 1, audit: 1, receipts: 1});
});
test('SQL-like task text remains data', async () => {
  const args = [...base]; args[3] = "TEST: '); DROP TABLE principal; --";
  await open(args);
  assert.equal((await db.query('SELECT description FROM public.approval_decision')).rows[0].description, args[3]);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM public.principal')).rows[0].n, 1);
});

for (const [table, column, value] of [
  ['approval_decision', 'description', 'changed outside the review'],
  ['approval_decision', 'risk_class', 'R0'],
  ['approval_request', 'risk_class', 'R0'],
  ['approval_request', 'response', 'approved'],
]) {
  test(`retry rejects altered ${table}.${column}`, async () => {
    await open();
    await db.query(`UPDATE public.${table} SET ${column}=$1`, [value]);
    await assert.rejects(open(), /review_no_longer_pending/);
    assert.deepEqual(await counts(), {decisions: 1, requests: 1, audit: 1, receipts: 1});
  });
}
