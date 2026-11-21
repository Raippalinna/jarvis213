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
4. Framtida fleranvändar-API: HTTPS POST med verifierad användaridentitet och token i Authorization/header, aldrig i URL. Den nuvarande Comet-endpointen är privat owner-only och inte ett färdigt multi-tenant-API.
5. Faktureras månatligt baserat på `jarvis_tenant_usage`

## Rickys egen tenant

- **Slug:** `ricky`
- **Plan:** Enterprise (kostnadsfri för ägaren)
- **Månadsbudget:** 500 kr Comet-kostnad
- **Alla 37 wiki-chunks** är taggade med denna tenant-id.


## Säkerhetsgräns för befintlig Comet-endpoint

Comet kräver HTTPS POST, JSON-body och `x-jarvis-key` i header. Tenant, user-id och Notion-destination är serverstyrda. En separat serverinställning `JARVIS_COMET_DISPATCH_ENABLED` måste vara exakt `true` innan vare sig anslutningskontroll eller normal dispatch kan köras; saknad eller annan inställning ger 423 utan backend- eller GitHub-anrop. GitHub Actions har dessutom en separat jobbnivågrind för `repository_dispatch` via `JARVIS_REPOSITORY_DISPATCH_ENABLED`. Dessa grindar ersätter inte användarautentisering eller tenantmedlemskap. Endpointen ska inte exponeras med delad nyckel i publik webbläsarkod eller erbjudas externa kunder.
