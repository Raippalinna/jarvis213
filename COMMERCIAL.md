# JARVIS Ω∞ OS — Kommersiell modell

## Prisplaner (från Supabase-tabellen `jarvis_license_plans`)

| Plan | Pris/mån | Anrop/mån | Max tier | Support | Custom agents | Whitelabel | Seats |
|---|---|---|---|---|---|---|---|
| **Free** | 0 kr | 50 | LOW | Community | ❌ | ❌ | 1 |
| **Pro** | 199 kr | 1 000 | MED | E-post | ❌ | ❌ | 1 |
| **Business** | 999 kr | 10 000 | HIGH | Prioritet | ✅ | ✅ | 5 |
| **Enterprise** | 4 999 kr | 100 000 | HIGH | Dedikerad | ✅ | ✅ + SLA 99.9% | 50 |

Alla planer inkluderar: Notion-postback, LangGraph supervisor, 3-lagers minne
(pgvector + Notion + wiki), Frugality Agent, autonoma cron-jobb.

## Multi-tenant-arkitektur

- `jarvis_tenants` — organisationer/kunder
- `jarvis_tenant_users` — användare med api_key_hash för autentisering
- `jarvis_license_plans` — 4 standardplaner
- `jarvis_tenant_usage` — månadsbaserad räkning per tenant
- `jarvis_memory.tenant_id` — isolerar semantiskt minne per kund

RLS är aktiverat, men fullständig tenantisolering är **inte driftverifierad**. En inskickad tenantparameter eller delad endpointnyckel är inte en verifierad identitet. För multi-tenant-drift krävs medlemskapskontroller, giltig användar-JWT och godkända negativa RLS-tester.

## Onboarding-flöde (framtida)

1. Kund registrerar sig via landningssida
2. Skapa tenant via edge-funktion → få unik `api_key`
3. Kund konfigurerar sin egen Notion-integration + Slack (eller använder vår SaaS-hosted)
4. Framtida fleranvändar-API: HTTPS POST med token i `Authorization` eller en dedikerad header, aldrig i URL. Utveckling av individuella användar-/tenantidentiteter och deras RLS-policyer måste föregå kundlansering.
5. Faktureras månatligt baserat på `jarvis_tenant_usage`

## Rickys egen tenant

- **Slug:** `ricky`
- **Plan:** Enterprise (kostnadsfri för ägaren)
- **Månadsbudget:** 500 kr Comet-kostnad
- **Alla 37 wiki-chunks** är taggade med denna tenant-id.

## Säkerhetsgräns för befintlig Comet-endpoint

Den privata owner-endpointen utvecklas mot `POST /functions/v1/jarvis-comet` med `x-jarvis-key` som header och JSON-body `{ "task": "...", "tier": "LOW" }`. Den accepterar inte längre anropsstyrda `tenant`, `user_id` eller `notion` när säkerhetsgrenen är driftsatt. Detta är **inte** multi-tenant-autentisering och ska inte erbjudas externa kunder utan en separat behörighetsmodell. Se [docs/comet-auth-hardening.md](docs/comet-auth-hardening.md).
