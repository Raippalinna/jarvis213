# Säkerhetspolicy – JARVIS Ω∞ OS

## Omfattning

Den här kodbasen hanterar GitHub Actions, API-nycklar, Supabase-åtkomst och
autonoma uppdrag. Det finns ingen verifierad publik release-/supportmatris.
Läs [autentiseringsdokumentationen](docs/authentication.md) före driftändringar.

## Rapportera sårbarheter

Rapportera en sårbarhet **privat** till repositoryägaren via GitHubs privata
sårbarhetsrapportering (om aktiverad) eller annan etablerad privat kontaktväg.
Lägg aldrig hemligheter, access tokens, fullständiga auth-headers, persondata
eller exploateringsdetaljer i en offentlig issue, PR eller chattlogg.

Ange berörd fil/commit, reproduktionssteg med syntetiska data, möjlig påverkan
och eventuell mitigering. Kalla inte en sårbarhet åtgärdad innan tester och
relevant driftverifiering har genomförts.

## Driftkrav

- Håll hemligheter i GitHub Actions Secrets / server-side secret stores.
- Ge PAT och databasroller minsta möjliga behörighet.
- Verifiera RLS/tenantisolering separat från lyckad autentisering.
- Bevara Approval Center, DRY_RUN, autonomispärr och kill switch.
- Roterade komprometterade hemligheter kan inte säkras enbart med kodändring.
- Granska alla ändringar i PR innan merge och inför separat produktionsgodkännande.
