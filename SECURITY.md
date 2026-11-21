# Säkerhetspolicy — JARVIS Ω∞ OS v2

## Omfattning och versioner

Projektet underhålls primärt på `main`. Separata releasegrenars stödstatus är inte fastställd här.
Säkerhetsförbättringar görs via separat branch, testning och granskad PR.
**Ingen PR är driftsatt enbart för att den har skapats eller fått gröna tester.**

## Rapportera en sårbarhet

Använd GitHubs privata **Report a vulnerability** / Security Advisory om funktionen är tillgänglig för repositoryt.
Publicera aldrig nycklar, tokens, JWT, användardata eller reproduktionssteg som exponerar produktionsmiljöer i ett publikt issue.
Om privat rapporteringsfunktion inte finns: kontakta repositoryägaren via en överenskommen privat kanal innan tekniska detaljer delas.

Lämna endast säkra reproduktionssteg med syntetiska credentials, observerat beteende, berörd commit/fil och bedömd påverkan.
Alla ändringar ska förankras hos repositoryägaren före merge och driftsättning.

## Grundregler

- `SUPABASE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `JARVIS_GITHUB_PAT`, LLM-nycklar och tredjepartstokens är endast för betrodda servermiljöer.
- Skicka aldrig credential-värden i URL:er, loggar, API-felmeddelanden, issues, testfixturer eller commits.
- Supabase publishable/anon-nycklar är inte backendadminbehörighet. Tenant-medlemskap måste valideras oberoende av ett inskickat tenant-id.
- Respektera `system_config.autonomy_enabled`, Approval Center och `DRY_RUN`. Ingen felsökning får kringgå dessa.
- Använd testnycklar och mockade nätverksanrop i CI. Live- och skrivprov kräver separat godkännande.
- Rotera en nyckel om den misstänks ha exponerats, och kontrollera anrops- och revisionsloggar.

Se [Autentisering och tokenflöden](docs/authentication.md) för nuvarande systemgränser, migreringssteg och kvarstående risker.
