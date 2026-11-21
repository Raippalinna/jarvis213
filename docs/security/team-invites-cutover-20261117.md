# JARVIS team_invites: säker cutover-plan (REVIEW ONLY)
Datum: 2026-11-17  
Spårning: [issue #88](https://github.com/rickyraippalinna/jarvis-omega-v2/issues/88)  
Databas: `fzmnqvmfilqizzftphbt` (`public.team_invites`)  
**Status: Skrivskyddade produktionsmetadata kontrollerade 2026-11-17. EJ TESTAT I STAGING. EJ DRIFTSATT.**

## Varför P1 prioriteras
Skrivskyddad metadata-kontroll har verifierat att `authenticated` får SELECT och UPDATE på `team_invites`, inklusive kolumnen `token`, samt att RLS-policyn för SELECT enbart kontrollerar `auth.uid() IS NOT NULL`. UPDATE-policyn gör samma kontroll utan separat ägarskap. Det är en behörighetsrisk med möjlig läsning av andras tokens och ändring av team/roll, inte bevis för faktiskt intrång. Tabellen har ingen verifierad utgångstid för inbjudningar; `created_at` finns, men ingen `expires_at`. Befintliga tokens är klartext i databasschemat och får inte skrivas till rapporter eller loggar.

## Omedelbara spärrar
- Inga produktionsändringar genom denna PR. Kör inte migrationsförslag direkt från dokumentation.
- Ingen `SELECT *` från `team_invites` under inventering. Läs metadata via `scripts/security/team_invites_acl_readonly.sql`; dumpa inga inbjudningstokens.
- Låt den gamla inbjudningsfunktionen förbli spärrad för utökad rollout tills ägarverifiering och klientinventering är genomförda. Gissa inte om tidigare klienter förlitar sig på direkt tabellåtkomst.
- Använd aldrig klientens `team_id`, `role`, `email`, `invited_by` eller `token` som auktoritetsbevis. Utgå från serververifierad Supabase Auth-identitet och en atomisk serverfunktion.

## Nödvändiga beslut före implementering
1. Inventera samtliga användningar av `team_invites` i frontend, backend, Edge Functions och tredjepartsintegrationer. Särskilt: läsning av `token`, acceptansflöde, teamägarens inbjudningslista och borttagning.
2. Bestäm produktkravet för godtagbar inbjudan: inloggad användare med verifierad e-postadress som matchar mottagaren, engångstoken, serverstyrd löptid och `accepted_at IS NULL`. Kräv att e-post är verifierad av Auth, inte användarstyrd metadata.
3. Bestäm vilken läsväg teamägaren behöver, exempelvis serverendpoint som returnerar `id, team_id, email, role, created_at, accepted_at` men aldrig rå token.
4. Bestäm revokeringsplan för potentiellt exponerade äldre tokens och kommunikation vid eventuellt incidentutfall. Ingen antagen exfiltration.
5. Staging/backup och en testad rollback till ett säkert läge krävs före produktionsbeslut.

## Föreslagen målarkitektur
- **Privat server-API** för att skapa/lista/återkalla inbjudningar: verifiera session och `teams.owner_user_id` på servern. Servern bestämmer tillåtna roller; ingen användare ska kunna självskriva `role` på en befintlig invite.
- **Atomisk acceptans** med verifierat auth-user-ID, verifierad matchning mot `auth.users.email`, kontroll mot maxlivslängd, engångstoken och `accepted_at IS NULL`. Transaktionen ska både registrera medlemskap och markera token använd, annars gör den inget. Ingen klient-SQL UPDATE mot `team_invites`.
- **Minsta rättighet**: efter verifierad migration, återkalla direkt `SELECT, UPDATE, DELETE, TRUNCATE, TRIGGER` från `anon` och `authenticated` på `public.team_invites`; avgör även behovet av INSERT först efter klientinventering. Fortsatta servervägar använder begränsad serverroll eller välgranskad RPC i icke-exponerat schema.
- **RLS och grants**: avveckla eller ersätt breda policyerna `Authenticated can read invites` och `User can accept their own invite`, kontrollera även `PUBLIC`-privilegier och default grants. Säkra funktionen mot IDOR, race conditions och search_path-kapning.
- **Datamodell**: gör `expires_at`/expiry-regel och tokenhashning till migrationsbeslut för nya inbjudningar. Bakåtkompatibilitet med befintliga poster måste bevisas, inte antas.

## Releasegrind: allt måste vara PASS
| Fall | Förväntat resultat |
|---|---|
| Anonym session listar/läser inbjudningar | DENY |
| Inloggad användare A läser B:s inbjudan/token | DENY |
| A ändrar B:s team, roll, e-post, token eller acceptanstid | DENY |
| A skapar inbjudan till team som A inte äger | DENY |
| Icke-verifierad eller felaktig e-post accepterar token | DENY |
| Förbrukad, utgången eller felaktig token | DENY, utan tillståndsändring |
| Två samtidiga acceptansförsök | Exakt ett kan lyckas, ingen dublett |
| Rätt mottagare accepterar giltig token | Ett medlemskap, en godkänd statusförändring |
| Teamägare listar egna inbjudningar | Endast egna, ingen rå token i svar |
| Efterkontroll av grants och RLS | Inga breda SELECT/UPDATE-vägar kvar |
| Appens existerande legitima klienter | Inga oförklarade fel |
| Backup/rollback | Testat i staging, även vid partiellt fel |

## Staging och driftsättning
1. Kör inventeringsskriptet och spara endast metadata/sammanfattning som begränsad artefakt.
2. Skapa syntetiska team A/B och separat Auth A/B med två olika verifierade mejladresser, inga riktiga kunder.
3. Implementera privata endpoints och databastransaktion i en separat gren. Kör verkliga negativa RLS-/API-tester, inte enbart statiska SQL-tester.
4. Migrera legitim klientkod i staging och verifiera att alla acceptanskriterier är PASS.
5. Förbered en **granskad** migrationsfil med återkallade grants och ändrade policies; säkerställ backup och återställning. Inga `CREATE POLICY USING(true)` som nödlösning.
6. Begär separat uttryckligt produktionsgodkännande. Frys skrivrutter under övergången, kör migrationen atomiskt och kontrollera grants, policyer och riktiga backendanrop.
7. Dokumentera exakt commit, tidpunkt, resultat och eventuella avvikelser. Vid fel: återställ till ett säkert låst läge, inte tidigare osäkra grants.

## Ny skrivskyddad verifiering 2026-11-17

En separat direkt katalogkontroll i det anslutna Supabase-projektet bekräftade: `team_invites` har RLS aktiverat; `authenticated` har SELECT och UPDATE; samma roll har SELECT på token och UPDATE på role; policyerna för bred SELECT och UPDATE använder endast `auth.uid() IS NOT NULL`. `auth.users` innehöll 0 användare och `jarvis_approval_admin` hade 0 aktiva medlemskap vid kontrollen. Det är katalogbevis för bristfällig auktorisering, inte ett lyckat API-angrepp eller läsning av token. SQL-källfilen i denna PR har ännu inte körts i sin helhet. Ingen schemaändring eller databasskrivning genomfördes.

## Dokumenterad verifiering
- GitHub issue #88 och läsning av PostgreSQL-kataloger ligger bakom riskbeskrivningen.
- Den här grenen innehåller endast dokumentation och skrivskyddad metadata-SQL.
- Ingen SQL kördes av denna PR, inga tester kördes och ingen produktionsmigrering utfördes.
- Supabase referens: https://supabase.com/docs/guides/database/postgres/row-level-security
