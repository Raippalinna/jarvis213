# JARVIS Ω∞ — releasegrind och ordning för GitHub-färdigställande

**Kontrollpunkt:** 2026-11-05. **Status:** källgranskning och CI-bevis, **inte** godkänd produktion. Dokumentet innehåller inga hemligheter eller körbara live-anrop.

## Varför ordningen är viktig

Flera öppna draft-PR:er ändrar samma autentiseringsyta. Att merga samtliga PR:er i nummerordning riskerar att återinföra osäkra URL-nycklar, äldre Supabase-backendauth eller inkompatibla klientkontrakt. En grön offline-CI-körning bevisar inte att autentiserad staging eller tenant-isolering fungerar.

| Prioritet | Förändring | GitHub-länk | Verifierad evidens | Kvar innan merge/deploy |
| --- | --- | --- | --- | --- |
| P0 | Supabase-backendnyckel och 401 | [PR #37](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/37), [issue #13](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/13) | Koden är förberedd i draft; inget bekräftat CI-resultat för exakt head vid kontrollpunkt | Read-only preflight, giltig backend-secret, RLS- och live-/stagingtest, CI |
| P0 | Dashboardautentisering | [PR #45](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/45) | [CI 42118361962](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42118361962) success | Klientmigrering till header, riktigt stagingtest, konfliktreview |
| P0 | Comet: header-POST, tenant och autonomigrind | [PR #47](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/47), [issue #43](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/43) | [CI 42123623970](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42123623970) success på head c89565e7... | Klientmigrering, verifierad backend-/tenantisolering i staging och review av upstream-åtkomst |
| P1 | Mission Engine dry-run | [PR #39](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/39) | [Offline CI 42114669805](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/42114669805) success | Kombinerad regression efter säkerhetsändringar och tydlig skillnad mellan plan och exekvering |

**OBS:** PR [#42](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/42) och [#44](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/44) överlappar PR #45. PR [#25](https://github.com/rickyraippalinna/jarvis-omega-v2/pull/25) är tidigare uppmärksammad som konfliktfylld; använd inte äldre PR som ersättning utan jämförelse av diff och ändringshistorik.

## Körordning (utan produktionseffekter)

1. **Frys referenserna** till aktuella head-SHA. Granska alla PR-diffar mot färsk `main`, inklusive överlapp och konfliktkandidater. Förväxla inte GitHub `mergeable=true` med säker driftsättning.
2. **Verifera #37** i nyckelfritt offline-CI och sedan en separat, auktoriserad read-only Supabase-stagingkontroll. Kontrollera `SUPABASE_SECRET_KEY` (modern `apikey`) kontra legacy service-role JWT. **Aldrig anon-nyckel som servernyckel.**
3. **Välj en dashboardlösning:** granska #42/#44 mot #45, behåll en sammanhängande implementering och släpp överlappande diffar. Bekräfta att klienten skickar `x-jarvis-key`, inte `?k=`; säkerställ att hemligheter inte lever i webbläsarens persistent storage.
4. **Anpassa faktisk Comet-klient innan #47:** `POST`, JSON-body, `x-jarvis-key`, utan querysträng, godtycklig tenant/user/Notion-destination eller GET-mutation. Rotera nyckeln om äldre query-string kan ha loggats.
5. **Autonomigrind och tenant:** testa negativt `autonomy_enabled=false`, saknad/401/otydlig status, falsk tenant, ändrad Notion-destination, dåligt JSON, överskriden payload, timeout, redirect och utebliven auth; testa positivt under godkänd stagingidentitet. Server-side bindning av identitet ska vara explicit; delad nyckel är inte individuell användaridentitet.
6. **Regressioner vid integrationsgren:** Python offline, dashboard TypeScript/build, alla Node-fixtures och sammanställd kvalitetsgrind måste vara gröna på exakt kandidat-SHA. Utvärdera effekten av #37 + #45 + #47 + #39 tillsammans.
7. **Separat RLS-release:** [jarvis-core issue #3](https://github.com/rickyraippalinna/jarvis-core/issues/3) har ett förberett men **inte exekverat** SQL-förslag. Granska grants, policies, SECURITY DEFINER och verkliga klienter innan migration. Kör inga SQL-förändringar utan separat explicit godkännande.
8. **Släppgrind:** begär explicit godkännande för exakt merge-sekvens, driftmiljö och eventuell secret-rotation. Dokumentera rollback, mättid och bevis. Först därefter merge/deploy.

## Icke förhandlingsbara kvalitetskriterier

- **Källa ≠ produktion:** Pull request, commit eller automatiska tester innebär inte att något kör i Perplexity, Comet, Slack eller Supabase.
- **Ingen tyst eskalering:** AI-agenters kostnad, rättighet, dataskrivning och externa meddelanden ska styras av policy och godkännanden.
- **Ingen blind bulk-merge:** Skilda PR:er kräver individgranskning, beroendeordning och versionskompatibilitet.
- **Nycklar i skyddat hemlighetslager:** varken GitHub-dokumentation, browser-URL:er eller testfixturer ska innehålla riktiga credentials.
- **Statusord:** `prepared`, `CI-verified`, `staging-verified`, `production-verified` och `released` får inte blandas ihop.

## Separata projekt som inte ska blockera Jarvis-releasen

- [Noumi OS PR #6](https://github.com/rickyraippalinna/noumi-mur-puts/pull/6): källåterställning, grön CI, men draft och ingen produktionsverifiering.
- [Green System Pro issue #4](https://github.com/rickyraippalinna/green-system-pro/issues/4): 2 859 ESLint-fel; build och tester gröna.
- [Sentinel Alert issue #4](https://github.com/rickyraippalinna/sentinel-alert/issues/4): 399 ESLint-fel; build och 19 tester gröna.
- Projektgränsen mot separat Perplexity-konto eller andra personers data kräver faktiskt verifierad behörighet; GitHub-åtkomst till ett repo bevisar inte Perplexity-åtkomst.

**Ägarskap för releasebeslut:** kontoinnehavaren. Ingen merge, deployment eller Supabase-migration utförs som del av denna dokumentations-PR.
