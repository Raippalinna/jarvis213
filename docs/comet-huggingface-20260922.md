# Comet and Hugging Face connection status

## Current result as of September 22, 2026, 18:16 UTC

**VERIFIED IN PRODUCTION for the read-only connection chain.** One approved
request authenticated through the Jarvis endpoint, triggered the isolated
GitHub check, and verified Hugging Face account `rickyraippalinna` plus 137 public
catalog entries; the run completed successfully at 18:16:50 UTC
([final connection check](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).

The job reported `completion_requests: 0`, `inference_tested: false`, and
`normal_jarvis_run: false`. Only `verify_connection` ran, not the ordinary Jarvis
runner, and the exact approved check ID was present in its sanitized output
([job and result](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505/job/106875915162)).

The approved endpoint-key replacement is complete. The same new key was saved
to production `JARVIS_ENDPOINT_KEY` and the personal Computer credential
`Jarvis Comet Endpoint`, using the `x-jarvis-key` header. The unrelated
`Jarvis Perplexity Router API` credential was not changed
([production secrets](https://supabase.com/dashboard/project/fzmnqvmfilqizzftphbt/functions/secrets)).

The positive authentication check returned **HTTP 200** and the no-credential
control returned **HTTP 401**, both with successful TLS verification. Supabase
invocation logs independently confirm both results on function version 6.
Neither request included a task, query parameters, or a body
([Jarvis endpoint](https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet)).

The earlier GET checks verified Computer-to-Jarvis authentication only; the
later, separately approved final check now also verifies the bridge's GitHub
dispatch capability. Native Comet shortcut configuration and paid model
inference remain outside that proof
([final check scope](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/integration/comet-hf-connectivity-20260922/docs/comet-hf-connection-check.md)).
Local Comet browser control was separately used during secure settings work,
and the browser-control session has been stopped without closing the user's tabs.

## Approved scope

The user approved a one-off credit purchase of at most USD 10 with no automatic
recharge. A later browser check already showed USD 12 in credits, an active PRO
account, and automatic recharge. No additional purchase was submitted by this
session. The user then specifically approved disabling recharge and creating
the two least-privilege credentials below. The PRO subscription was left unchanged.

## Verified saved settings

- **Hugging Face billing:** the browser check earlier on September 22 showed
  USD 12 in credits and no automatic recharge configuration after the approved
  change; this is the last observed balance, not a new billing read after the
  final connection test ([Billing](https://huggingface.co/settings/billing)).
- **Hugging Face token:** `jarvis-omega-v2-inference` has only
  `Make calls to Inference Providers`; it was stored as `HF_TOKEN` in the existing
  repository's Actions secrets and the saved name was read back through both the
  UI and GitHub CLI ([Actions secrets](https://github.com/rickyraippalinna/jarvis-omega-v2/settings/secrets/actions)).
- **GitHub token:** `Jarvis Comet bridge 2026-09-22` expires October 22, 2026.
  Its only selected repository is `rickyraippalinna/jarvis-omega-v2`, with Contents
  read/write and mandatory Metadata read-only
  ([token settings](https://github.com/settings/personal-access-tokens/19987507)).
- **Supabase:** `JARVIS_GITHUB_PAT` was saved and read back as a named row in
  production project `fzmnqvmfilqizzftphbt`. Under a later, separate approval,
  `JARVIS_ENDPOINT_KEY` was replaced and synchronized with the Computer vault;
  the old server value was not read
  ([Edge secrets](https://supabase.com/dashboard/project/fzmnqvmfilqizzftphbt/functions/secrets)).

Contents write is required by GitHub's repository-dispatch endpoint. It also
permits repository content changes, so the token is repository-scoped and
time-limited ([GitHub REST documentation](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event)).

## Read-only runtime test

The existing `jarvis-cloud.yml` workflow now has an opt-in
`verify_huggingface` input on the development branch. When true, it skips the
normal Jarvis runner and executes only `scripts/huggingface_preflight.py`.
The job receives HF_TOKEN but no Supabase, Notion, Slack, or CometAPI credentials.

The script checks the token against `GET /api/whoami-v2`, requires the expected
account, and separately reads the public model catalog. Redirects are rejected;
credentials, response bodies and raw exception messages are never logged
([Hugging Face API](https://huggingface.co/.well-known/openapi.md),
[catalog documentation](https://huggingface.co/docs/inference-providers/en/hub-api)).

Catalog access is public and does not prove inference authorization or paid model
execution. The script reports `inference_tested: false` and performs no completions,
credit purchases, memory writes, notifications, or background scheduling.

## Observed test results

At 2026-09-22 11:57:33 UTC, the manually dispatched verification job succeeded
on commit `cd152eb9acdb51d27eab9589230c4da8e0a70fd4`. Its sanitized report was
`identity_and_catalog_verified`, account `rickyraippalinna`, 137 catalog models,
`completion_requests: 0`, and `inference_tested: false`. The separate normal
`execute` job was **skipped**
([verification run and job logs](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35724343324)).

The existing offline regression workflow also passed for the same commit
([PR regression run](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35724349467)).
The 11 focused preflight unit tests had already passed locally before the push.
These results verify the stored HF token's identity access from GitHub Actions,
not inference execution or the separate GitHub PAT's runtime dispatch capability.

At that earlier stage, production main was still
`e177f8fbfacedb85bc8cb6522a33fb5de5021ec9`. The later final-check approval deployed
only the isolated commit `5447661e92a9638bd23b158cc651ef0b4176fdad`, not the larger
development branch
([isolated production commit](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/5447661e92a9638bd23b158cc651ef0b4176fdad)).

## Historical Comet authentication diagnosis

The user chose to keep the existing endpoint key and supplied it through secure
credential entry on September 22. The first Computer credential record was then
removed and recreated with explicit approval; the second saved record is in the
personal/user vault, not session-only storage. At that stage, no endpoint key
had been rotated.

The subsequent HEAD and GET authentication checks returned HTTP 401 after TLS
certificate verification succeeded. Neither request contained a task or query,
and response bodies were discarded. An earlier unauthenticated control also
returned HTTP 401
([Comet endpoint](https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet)).

The second record also returned HTTP 401 at 12:50:48 UTC. The server's invocation
log confirmed that the request reached function version 3. Ordinary logs cannot
distinguish a missing custom authentication header from a wrong value, because
Supabase logs only an allowlist of headers
([Supabase logging documentation](https://supabase.com/docs/guides/observability/advanced-log-filtering)).

At 15:02 Europe/Stockholm, the user explicitly approved one temporary
boolean-only diagnostic, one no-task GET and immediate restoration. The
diagnostic was locally regression-tested across 21 fixtures without network
requests, deployed as version 4 and read back byte-for-byte before use. Its
hard expiry was 16:00 Europe/Stockholm on September 22.

The single marked GET at 13:04:23 UTC returned HTTP 401 with TLS verification
result 0. Its one valid JSON log event reported:

```json
{
  "event": "jarvis_auth_probe_20260922_v1",
  "expected_key_configured": true,
  "header_received": true,
  "authenticated": false
}
```

This proved that the server key was configured and the `x-jarvis-key` field
arrived, but its value did not match the server key at the time. It did not reveal
either value or explain why they differed. No key value, length, hash, request URL, body
or personal data was logged
([Comet endpoint](https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet)).

The exact original source was restored immediately as version 5 and read back.
The restored file matches the version-3 original byte-for-byte, with source-file
SHA-256 `00ae20b8e39d2550fe336a424794c57f45b6c2be13cb28618c6cd62e436fe40c`
and unchanged `verify_jwt=false`. The temporary diagnostic is no longer deployed.
The original and restored source hashes are code hashes, not credential hashes.

## Approved key replacement and final authentication checks

At 15:26 Europe/Stockholm, the user explicitly approved replacement on exactly
two destinations: the Supabase `JARVIS_ENDPOINT_KEY` and the personal Computer
`Jarvis Comet Endpoint` credential. The old Computer record was removed, a new
shared value was entered in the secure fields, and both saved destinations were
verified. The Supabase row showed an update at 13:30:52 UTC. No other credential,
billing setting, subscription, or production source code was changed by this
replacement
([Supabase secrets](https://supabase.com/dashboard/project/fzmnqvmfilqizzftphbt/functions/secrets)).

The successful request was recorded at **17:31:57.574 UTC**, status 200.
The no-credential control was recorded at **17:33:13.069 UTC**, status 401.
Both were GET requests to the bare endpoint, with response bodies discarded.
The authenticated request used the saved header credential, not a key in a URL.
The client reported TLS verification result 0 for each
([Jarvis endpoint](https://fzmnqvmfilqizzftphbt.supabase.co/functions/v1/jarvis-comet)).

Production version 6 was read back and still matches the original source
byte-for-byte, with SHA-256
`00ae20b8e39d2550fe336a424794c57f45b6c2be13cb28618c6cd62e436fe40c`.
The temporary diagnostic remains absent. The historical failed-probe evidence
is preserved separately and is not rewritten as a success.

## Approved final deployment and live verification

At 20:11 Europe/Stockholm, the user separately approved the isolated connection
package and exactly one event. Main was fast-forwarded only to
`5447661e92a9638bd23b158cc651ef0b4176fdad`; the existing ordinary workflow and
Python runner were unchanged, and the larger reliability PR remains unmerged
([deployed change](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/5447661e92a9638bd23b158cc651ef0b4176fdad),
[unmerged PR](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/2)).

`jarvis-comet` was deployed as ACTIVE version 7 and read back byte-for-byte
against the approved source, whose code SHA-256 is
`e579d8656fad3859638d243686bb726a95f4d8226118a3aabe408fe8f5f39187`.
Custom-header authentication was preserved, and the new path enforces the
existing autonomy stop before dispatch without changing its stored value
([deployed source and tests](https://github.com/rickyraippalinna/jarvis-omega-v2/commit/5447661e92a9638bd23b158cc651ef0b4176fdad)).

The only POST returned HTTP 202 with TLS verification result 0; Supabase logs
recorded it at 18:16:41.483 UTC on version 7. The check ID
`cc62340c-98bc-409b-9a40-6523e1eade84` then appeared in the single successful
`repository_dispatch` run at the expected commit
([correlated live result](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).

The public catalog is not evidence of paid inference access. The successful job
verified identity and catalog access only, with zero completion requests
([sanitized HF result](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505/job/106875915162)).
The complete scope, rollback baseline and separate historical/local versus live
evidence are retained in the final-check document
([final-check record](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/integration/comet-hf-connectivity-20260922/docs/comet-hf-connection-check.md)).

## Remaining production boundary

The endpoint-key mismatch and the untested bridge-dispatch link are
**resolved**, but the normal production workflow still does not load `HF_TOKEN`
or route ordinary tasks through Hugging Face
([unchanged production workflow](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/main/.github/workflows/jarvis-cloud.yml)).
No paid model was activated, no normal task or Notion delivery was tested, and
native Comet `/jarvis` shortcut configuration was not established by this
header-authenticated Computer check
([test boundary](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/integration/comet-hf-connectivity-20260922/docs/comet-hf-connection-check.md)).

Do not request another key entry, rotate again, broaden permissions, merge the
larger reliability PR, or enable a paid provider implicitly. The documented
production safety gates remain in force. No model-quality score, pricing
assumption, spend balance, or fallback was invented.

## Rollback

The approved failure rollback for the final check was limited to restoring the
original Edge source and reverting only its isolated GitHub package. It was
not needed because the live check succeeded; no new rollback or test is
automatically authorized by retaining these instructions
([successful run](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/35766104505)).
The earlier development-branch HF diagnostic and the temporary Comet auth
diagnostic are separate historical changes. The temporary auth diagnostic was
already removed by the verified restoration to version 5; its one-probe
approval is consumed.
The old server key was not read and cannot be automatically restored. Clients
using the previous key must be updated through secure credential storage;
never place the new key in a browser shortcut, document, or chat.
Credential revocation or billing changes require a separate explicit decision;
never re-enable automatic recharge as an automatic rollback.
