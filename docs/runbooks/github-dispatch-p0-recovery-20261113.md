# P0 – Säker återställning av GitHub repository_dispatch (2026-11-13)

Källa: [issue #70](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/70). Senaste dokumenterade driftbeviset är HTTP 401 från GitHub för serverlagrad `JARVIS_GITHUB_PAT` den 7 november. Detta dokument bevisar **inte** att felet fortfarande finns i drift.

## Beslut före åtgärd

1. **Ingen automatisk tokenrotation.** Kontoinnehavaren måste själv bekräfta rätt GitHub-identitet, repoåtkomst och om GitHub App-installationstoken eller finfördelad PAT ska användas.
2. Kontrollera GitHubs officiella dokumentation för `repository_dispatch` och tokenbehörigheter vid rotation. Begränsa token till detta privata repo och nödvändiga behörigheter. Använd inte klassisk PAT med bredare åtkomst som genväg.
3. Uppdatera endast den befintliga serverlagrade hemligheten via auktoriserad secret-hantering; visa aldrig token i chatt, terminalutskrift, PR, loggar eller dokument.
4. Utför **en** isolerad, uttryckligen godkänd `verify_connection`-kontroll, inte `jarvis-run`, och kontrollera att inget betalt modell-API, extern notifiering eller annan agentkörning startar. Stoppa efter ett misslyckande; undvik loopar.
5. Kontrollera GitHub-svar och serverlogg med maskerade uppgifter. Förväntat för lyckad `repository_dispatch`: HTTP 204 från GitHub. Bekräfta även rätt repo och att endast avsedd diagnostik körts.
6. Dokumentera tid, maskerad körningsidentifierare, HTTP-status, aktuell konfiguration och eventuell rollback i `docs/evidence/` **utan secrets**. Verifiera att befintliga kill switch-, approval- och DRY_RUN-regler är oförändrade.

## Alternativ utan nya kostnader

- **A:** Befintlig GitHub-anslutning för read-only diagnos och kod/PR. Den kan inte antas ersätta den separata serverlagrade token.
- **B:** Branch + offline-test och granskning av dispatch-kontraktet. Kan förberedas utan Lovable-krediter, men kan inte bevisa produktionens token.
- **C:** Lokal, nyckelfri simulering av felkod 401/204 och återhämtningslogik. Kan inte reparera autentisering på GitHub.
- **D:** Nya krediter är inte relevanta för detta behörighetsfel.

## Verifieringsmatris

| Kontroll | Status 2026-11-13 |
| --- | --- |
| Historiskt 401-fel | Dokumenterat i issue #70 |
| Aktuell tokenbehörighet | EJ VERIFIERAT |
| Aktuellt kreditsaldo | EJ VERIFIERAT |
| Produktionens dispatch efter rotation | EJ VERIFIERAT |
| CI/build för detta dokument | EJ VERIFIERAT |

**Återställning:** Stäng dokumentations-PR utan merge. Ingen produktionskod, RLS, secrets, budget eller deployment ändras av denna PR.
