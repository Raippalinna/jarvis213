# Jarvis API and safety completion

This is a continuation of the existing reliability branch, not a new Jarvis.
Status: 70 offline tests pass locally, pending remote CI and production review. No credentials,
billing settings, database migrations, schedules or production branches are changed.

## Implemented

- **Kill switch:** `system_config` is read before the graph and immediately before
  each Python model call, memory insert, approval insert, notification and briefing
  write. Only the observed TEXT value `true` permits execution. Missing access,
  ambiguous rows, disabled state, dry-run and network errors stop side effects.
  There is no cache and no environment bypass for an unavailable switch.
- **Budget routing:** missing or invalid spend input does not mean zero.
  A budget veto cannot be overridden by sensitivity escalation. FREE never falls
  back to a paid model; no policy-blind last-resort route remains.
- **Fallback accounting:** an estimated reservation is retained for timed-out calls,
  and the next attempt must fit the remaining per-run estimate. Observed usage is
  accumulated even for empty or truncated responses. Unknown costs stay flagged.
- **LOW compatibility:** the already configured Comet GPT-4o candidate can be used
  only if it satisfies the unchanged LOW quality, privacy and estimated cost limits.
  No quality floor or spending cap was lowered or raised.
- **Memory:** trusted deployment configuration supplies a tenant and an auth-user
  UUID. The existing `tenant_id` AND `user_id` columns are filtered server-side.
  Unknown ownership is excluded; the old unscoped vector RPC and embedding calls
  are not used. Missing scope disables all memory, not the authorization check.
- **Shared context:** legacy Notion/wiki sources default off. Explicit enabling
  also requires confidential clearance. Retrieved labels are preserved on
  reflection; writing an innocuous-looking summary cannot downgrade its label.
- **Outputs:** common credential formats are redacted at logging/notification
  boundaries; this is not exhaustive PII detection. Auto-classification is no
  longer logged as an executed action. Notion append uses PATCH, and requested
  briefings require a content readback before receiving a success status.
- **Perplexity Router:** an explicit opt-in adapter and read-only model-catalog
  verifier are implemented. No model IDs, quality measurements or exchange rates
  are invented. Unknown/stale catalog entries block configuration.

## Perplexity setup contract

The documented base URL is `https://api.perplexity.ai/router/v1`, authenticated
with a Bearer key; `GET /models` returns IDs and token pricing
([Perplexity Router quickstart](https://docs.perplexity.ai/docs/gateway/quickstart)).

1. Save an active key as `PERPLEXITY_API_KEY` in the actual runtime secret store.
   A credential saved in Computer is not automatically a GitHub Actions secret.
2. Fetch a catalog without running a completion:
   `python scripts/perplexity_preflight.py --output router-models.json`.
   A credential-injecting HTTPS proxy can use the explicit `--proxy-credential`
   option; it never prints the key or disables TLS verification.
3. Configure `JARVIS_ROUTER_MODELS_PATH`, `JARVIS_PERPLEXITY_MODEL`,
   `JARVIS_ROUTER_TIER`, `JARVIS_ROUTER_USD_SEK` and a locally evaluated
   `JARVIS_ROUTER_QUALITY_INDEX`. Catalogs expire after 24 hours; there is no
   automatic refresher in this release.
4. Review data handling before setting `JARVIS_ROUTER_DATA_APPROVED=1`.
   The adapter still refuses confidential and secret material. Its conservative
   policy flag is not an assertion about the provider's retention practices.
5. Only after runtime credentials, credit/access and routing are verified should
   `JARVIS_ENABLE_PERPLEXITY=1` be considered. No purchase or automatic refill is
   included in this change.

Prices in USD per million tokens become SEK per thousand tokens by multiplying by
the configured USD/SEK assumption and dividing by 1,000. Cache discounts are not
assumed. Configuration prices and observed token counts remain estimates, not invoices.

## Reproduction

```sh
python -m pip install -r requirements.txt
PYTHONPATH=src:. python -m unittest discover -s tests -v
git diff --check
```

The tests use fake keys, fake network clients and explicit switch decisions.
They cover all tiers, a full LOW graph turn, kill-switch transitions, blocked
side-effect boundaries, identity mismatch, empty clearance, Router opt-in,
catalog staleness, unit conversion, accumulated fallback reservations and Notion
readback. Passing them is not a live provider or production verification.

## Open production gates

- **Monthly ledger:** no authoritative live spend feed or atomic cross-run budget
  reservation exists yet. `JARVIS_MONTH_SPEND_PCT` must come from a trusted current
  meter; setting it to `0` manually is not a fix. The monthly memory audit is
  explicitly not a billing ledger. Provider-side spending controls remain needed.
- **Ownership:** the live schema has nullable `tenant_id` and `user_id`; this
  release does not migrate/backfill existing rows or invent their owner.
  RLS and server-side identity binding still need an independent review before
  exposing this trusted-runner API to other users.
- **Provider availability:** all existing Comet model IDs, prices and quality
  scores remain configuration assumptions pending live account checks.
- **Typed actions:** keyword approval remains an incomplete classifier, not
  authorization to send arbitrary messages, spend money or execute arbitrary tools.
- **Other runtimes:** the guard applies to this Python repository only. It does
  not retrofit the separately deployed Supabase Edge Functions or n8n workflows.
- **Notifications:** content readback is implemented for the requested cloud
  briefing. Generic alert receipts are not represented as verified end-to-end flows.

Supabase privileged server keys bypass RLS, so application scope checks must not
be described as a replacement for database authorization
([Supabase API keys](https://supabase.com/docs/guides/api/api-keys)).

## Rollback and promotion

Keep `main` unchanged until the exact production scope is approved and the open
gates are resolved. This patch has no database migration and deletes no data.
Revert its commit on the same branch to restore the previous candidate.
Do not re-enable the legacy unscoped memory path merely to recover old records.
