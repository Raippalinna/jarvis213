# P1: ta bort URL-nyckel från JARVIS Brain och minimera public mode

Datum: 2026-11-17  
Projekt: Supabase fzmnqvmfilqizzftphbt  
Relaterat ärende: https://github.com/rickyraippalinna/jarvis-omega-v2/issues/90

## Verifierat före ändring

- jarvis-brain är ACTIVE version 1 med verify_jwt=false.
- Den gamla funktionen accepterar x-jarvis-key eller query-parametern k.
- Full-läget returnerar system_config, senaste minnesposter med innehåll, körningar, approvals, connector-health och tenant usage.
- Public mode returnerar aggregerade räknare, eventtyper och minneskällor.
- Funktionen är read-only; service_role används server-side.

## Ändring i denna PR

- Avvisa alla query-parametrar före autentisering eller databasåtkomst.
- Acceptera privat nyckel endast i x-jarvis-key-header.
- Felaktig header ger 401.
- Public mode returnerar endast ok/mode/generated_at/read_only/status och gör inga databasfrågor. Privat backend är låst till exakt Supabase-origin, endast service_role/sb_secret-nyckel accepteras och redirects avvisas.
- Full mode behåller aggregerad read-only status bakom headernyckeln; råa system_config-värden, minnesinnehåll, approval-rader och tenant-usage exponeras inte.
- CORS-preflight och no-store bevaras.
- Inga skrivningar eller hemligheter läggs till i källkod.

## Viktig begränsning

Header-baserad delad nyckel är en mellanlösning. Starkare slutläge är Supabase Auth JWT plus aktiv jarvis_approval_admin-medlemskap, men produktionskontrollen 2026-11-17 visade noll aktiva adminmedlemskap. Full-läget bör flyttas till den modellen när en ägaridentitet är verifierad och provisionerad.

## Nyckelrotation

Om den gamla nyckeln har skickats i URL måste den roteras i Supabase Secrets och hos alla godkända klienter. Inga nyckelvärden eller URL-loggar hämtades i denna granskning; faktisk historisk exponering är därför okänd. Rotation görs inte i denna PR.

## Driftsättning

1. Kontrollera klienterna och uppdatera dem till x-jarvis-key-header.
2. Rotera nyckeln om URL-användning kan ha förekommit.
3. Deploya funktionen med nuvarande verify_jwt=false endast eftersom public health-mode är avsiktligt; privat full-mode kräver headernyckeln.
4. Testa utan query, med ?k=, med fel header, utan header, med rätt header och OPTIONS i staging.
5. Verifiera att public mode inte returnerar räknare, händelsetyper, minnesmetadata eller systemkonfiguration.

Ingen deployment eller nyckelrotation har gjorts.

Status: FÖRBERETT FÖR AKTUELL MAIN / EJ DRIFTSATT.
