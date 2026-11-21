# Produktionsbevis: Jarvis RLS-härdning 2026-11-07

**Utfört via ansluten Supabase på projektet `fzmnqvmfilqizzftphbt`.**
Detta dokument återger *redan tillämpade* migrationer. Kör inte SQL från
dokumentet en gång till. Inga hemligheter eller raddata har lästs eller lagrats.

## Tillämpade migrationer

### 1. `jarvis_memory_audit_write_lockdown_20261107`
Supabase migrationshistorik: `20261107010204`.

- Tog bort policyn `jarvis_backend_insert_audit`, som tillät
  `INSERT TO anon, authenticated WITH CHECK(true)`.
- Tog bort skrivprivilegier för `anon` och `authenticated` på
  `public.approval_audit_log`; `service_role` behåller behörighet.
- Tog bort `jarvis_backend_insert_memory`, som tillät anonym insättning.
- Tog bort den allmänt tillgängliga `jarvis_memory_owner_write`, där
  `user_id IS NULL` tidigare innebar att null-scopade rader gick att skriva.
- Ersatte med separata `INSERT`, `UPDATE`, `DELETE`-policyer för
  `TO authenticated`. `auth.uid()` måste vara skild från NULL och
  matcha `jarvis_memory.user_id`. INSERT/UPDATE förbjuder
  `sensitivity = 'secret'`.
- Begränsade `jarvis_memory_owner_select` till `TO authenticated`,
  men behöll dess tidigare läsvillkor tills tenantkopplingen kan migreras.
- Återkallade `anon`-privilegier på `public.jarvis_memory`.

**Verifierat via metadata efter migrationen:** `anon` saknar SELECT/INSERT/
UPDATE/DELETE på båda tabellerna; `authenticated` saknar samma behörigheter
på revisionsloggen; `service_role` behåller dessa. Policyerna och deras
`USING`/`WITH CHECK` har lästs tillbaka.

**Databevarande:** 77 minnesrader före och efter migrationen. Inga rader
ändrades eller togs bort; inga produktionsskrivtester genomfördes.

### 2. `jarvis_system_config_authenticated_read_allowlist_20261107`

Begränsade policyn `Authenticated users can read system config` till
`TO authenticated`, `auth.uid() IS NOT NULL` och en explicit lista över
sex icke-hemliga nycklar:

- `admin_domain`
- `autonomy_enabled`
- `linear_auto_issue_enabled`
- `slack_alert_events`
- `slack_alerts_channel`
- `slack_health_channel`

`dashboard_password_sha256` ligger **utanför** denna läslista.
Administratörspolicyn `Admins can manage system config` är oförändrad.
Metadata efter migrationen bekräftar detta. Sju av sju config-rader finns kvar.

## Uppföljning / resterande risker

1. **Tenantisolering ej färdig:** alla 77 befintliga `jarvis_memory`-rader
   saknar `user_id`, och 40 saknar `tenant_id`. Nuvarande
   `jarvis_memory_owner_select` tillåter alltjämt autentiserade användare
   att läsa rader med `user_id IS NULL`, förutsatt SQL-grant. Denna
   gemensamma läsväg måste fasas ut efter korrekt datamigrering och
   användar-/tenantmedlemskapsmodell.
2. **Backend-hemlighet (#13 / PR #37):** live-autentisering från GitHub
   Actions och verklig service-role-åtkomst är inte bekräftad genom dessa
   SQL-metadatafrågor. Kör separat skrivskyddad diagnos och därefter
   godkänt skriv-/återläsningsprov.
3. **Om applikationsflöden förlitade sig på anonym direktinmatning** till
   minne eller revisionslogg kommer de nu att nekas. Rätt lösning är
   server-side privilegierad åtkomst eller individuella sessioner med
   validerat tenantmedlemskap, inte att återinföra vidöppna policyer.
4. **Dashboard/Comet Edge Functions:** GitHub-PR:erna #45 och #67 är
   ännu inte driftsatta. De måste migreras och verifieras separat.
5. **Övriga Supabase Security Advisors** kräver separat riskklassning.
   Varningar om GraphQL-grants är inte i sig bevis på dataläckage när RLS
   blockerar rader, men bör utredas.

## Verifiering utan dataläckage

```sql
SELECT tablename, policyname, cmd, roles, qual, with_check
FROM pg_policies WHERE schemaname='public'
AND tablename IN ('jarvis_memory','approval_audit_log','system_config')
ORDER BY tablename, policyname;

SELECT has_table_privilege('anon','public.jarvis_memory','INSERT') AS anon_memory_insert,
       has_table_privilege('anon','public.approval_audit_log','INSERT') AS anon_audit_insert,
       has_table_privilege('service_role','public.jarvis_memory','INSERT') AS backend_memory_insert;
```

## Återställning

Ändringarna har ingen data-rollback eftersom ingen data ändrades. En eventuell
policyåterställning måste utformas mot aktuell drift- och klientstatus i en ny
granskad migration. **Återinför inte tidigare `WITH CHECK(true)` för anonym
revisionloggning eller `user_id IS NULL` i en generell skrivpolicy.**


## Upprepad verifiering 2026-11-07 (skrivskyddat)

Samtliga verifieringar mot verkligt Supabase-projekt, inga credentials eller
känsliga radvärden extraherades:

- Simulerad PostgreSQL-roll `authenticated` med ett syntetiskt,
  icke-existerande JWT-sub-ID (test-ID `11111111-1111-4111-8111-111111111111`)
  gav `count(*) = 77` för `public.jarvis_memory`, dvs 77/77 minnesrader
  läsbara med den historiska RLS-grenen `user_id IS NULL`. Testet använde
  `BEGIN READ ONLY`, `SET LOCAL ROLE` och `ROLLBACK`. Detta verifierar
  ett **cross-user-läsglapp** i databasens RLS, men är inte ett riktigt
  Supabase JWT/HTTP-test och visar inte att data faktiskt missbrukats.
- Samma syntetiska användare såg **0** rader med
  `key='dashboard_password_sha256'` i `public.system_config` och
  **6** icke-hemliga konfigureringar; allowlist-policyn fungerar.
- Antal efteråt: 77 minnesrader (77 med null `user_id`, 40 med null
  `tenant_id`), 39 revisionsloggar, 7 konfigureringar.
- `jarvis_memory_search` är `SECURITY INVOKER` (`prosecdef=false`).
  `anon` har EXECUTE-grant på funktionen men saknar tabellens
  läsprivilegier; faktisk RPC-åtkomst måste testas separat.
- Sju Edge Functions är ACTIVE, inklusive separata
  `jarvis-comet-secure` och `jarvis-dashboard-secure`. Deployad
  kanarykod matchar respektive GitHub-branch byte för byte.
- Externa HTTP GET utan credentials mot båda kanarierna gav HTTP 401,
  bekräftat också genom Supabase `function_edge_logs`.
  Detta bevisar **inte** att en giltig nyckel ger en fungerande session.
- PR #37 körde unit-tests men dess särskilda
  `live-read-only-preflight` var **SKIPPED**. Supabase-backendnyckeln
  i GitHub Actions är därför inte driftverifierad.

**Säkerhetsbedömning:** innan individuella användare eller externa tenants
får åtkomst måste den historiska läsgrenen `OR user_id IS NULL`
avlägsnas/ersättas efter att den privilegierade serverläsningen och
legacy-klienterna kontrollerats. Se [issue #69](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/69).
