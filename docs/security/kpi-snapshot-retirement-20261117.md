# P0: privat KPI-snapshot och borttagning av publik service-role-skrivväg

Datum: 2026-11-17  
Projekt: Supabase fzmnqvmfilqizzftphbt  
GitHub: rickyraippalinna/jarvis-omega-v2  
Relaterat ärende: https://github.com/rickyraippalinna/jarvis-omega-v2/issues/89

## Verifierat före ändring

Skrivskyddad kontroll av produktionsmetadata och Edge Function-källkod visade:

- jarvis-kpi-snapshot är ACTIVE, version 3, verify_jwt=false.
- Funktionen initierar Supabase-klienten med SUPABASE_SERVICE_ROLE_KEY.
- Funktionen skriver till memory_episode och event.
- cron.job innehåller aktivt jobb jarvis-kpi-snapshot, ägare postgres, schema 0 */2 * * *.
- Jobbkommandot anropar Edge Function via HTTP och saknar Authorization-header.
- vault.secrets är tom; ingen befintlig Vault-hemlighet kan användas för denna körväg.
- pg_cron, pg_net, supabase_vault och pgcrypto är installerade.
- event.idempotency_key har ett unikt index.
- public.dead_letter saknar tenant_id; KPI-funktionen får därför inte räkna globala dead-letter-rader i en enskild tenants snapshot. Måttet returneras som null med dead_letters_scope=not_tenant_scoped.
- `public.dead_letter` saknar `tenant_id` i aktuell produktionsschema; KPI-snapshoten ska därför rapportera detta mått som ej tenant-scope:at (`null`) tills schemat får en verifierad tenant-koppling. Den får inte räkna globala dead-letter-rader i en tenants snapshot.
- De relevanta kolumnerna i memory_episode, event, entity, approval_decision och dead_letter har lästs från katalogmetadata; inga privata rader eller tokenvärden hämtades.

## Föreslagen lösning i denna PR

1. Flytta KPI-beräkning och skrivning till en SECURITY DEFINER-funktion i PostgreSQL.
2. Sätt en låst search_path och kvalificera alla tabellnamn.
3. Äg funktionen med postgres; återkalla körbehörighet från PUBLIC, anon, authenticated och service_role; ge endast postgres EXECUTE.
4. Använd transaktionslås per tvåtimmarsfönster och en stabil idempotency key.
5. Rapportera dead_letters som null tills en verifierad tenant-koppling finns; räkna aldrig globala dead_letter-rader för en tenant.
5. Låt pg_cron anropa funktionen direkt, utan publik HTTP-ingress.
6. Gör den gamla Edge Function till en 410-tombstone utan service-role-klient och sätt verify_jwt=true.

## Driftsättningsordning (kräver separat godkännande)

1. Kör i staging först om sådan miljö finns och är isolerad.
2. I ett kort underhållsfönster: deploya tombstone-funktionen med JWT-verifiering aktiverad. Anonyma anrop ska få 401 från gateway; autentiserade anrop får 410.
3. Applicera migrationen som ersätter cron-jobbet med den privata PostgreSQL-funktionen.
4. Kör funktionen en gång manuellt som postgres för att täcka eventuell schemaläggningslucka.
5. Läs tillbaka cron.job: exakt ett aktivt jobb, username=postgres, command=SELECT public.jarvis_kpi_snapshot();, schema 0 */2 * * *.
6. Kontrollera körresultat, memory_episode/event-idempotens och Security Advisor. Utför inga anonyma skrivtester mot produktionsdata.

## Återställning

Återställ inte den tidigare publika service-role-Edge Function eller HTTP-cronvägen. Om den privata funktionen misslyckas: avaktivera det nya cron-jobbet, behåll tombstone-funktionen, felsök i staging och återställ endast en granskad privat DB-version. En utebliven KPI-snapshot är säkrare än en publik privilegierad skrivväg.

## Teststatus

- Offline statiska kontrakttester tillagda i tests/test_kpi_snapshot_security.py.
- Befintlig jarvis-code-quality.yml kör hela Python-sviten utan nätverk vid PR.
- SQL-migrationen har inte applicerats; Edge Function har inte deployats; produktionsdrift är inte verifierad.

Status: FÖRBERETT PÅ SEPARAT BRANCH / EJ DRIFTSATT / INGEN PRODUKTIONSÄNDRING.
