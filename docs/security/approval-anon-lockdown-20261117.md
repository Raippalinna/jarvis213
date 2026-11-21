# P0: stäng direkt anon-åtkomst till Approval Center

Datum: 2026-11-17  
Projekt: Supabase fzmnqvmfilqizzftphbt  
Relaterat ärende: https://github.com/rickyraippalinna/jarvis-omega-v2/issues/52

## Aktuell verifierad status (skrivskyddad)

- anon och authenticated har fortfarande breda tabellgrants på approval_decision och approval_request, inklusive INSERT/SELECT/UPDATE.
- Kända RLS-policies tillåter anon-INSERT/SELECT/UPDATE för approval_decision och anon/authenticated-INSERT för approval_request.
- approval_audit_log har inga anon/authenticated-grants i den lästa metadataresponsen; migrationen återkallar ändå dessa explicit.
- Den serverbaserade ApprovalGate i JARVIS använder SUPABASE_SERVICE_ROLE_KEY från servermiljön, inte från klienten.
- RPC public.jarvis_approval_decide(uuid,uuid,text,text) finns, är SECURITY DEFINER, ägs av postgres, har låst tom search_path och kan köras av service_role men inte anon/authenticated.
- Edge Function jarvis-approval-admin finns och verifierar Supabase Auth-användaren samt kontrollerar medlemskap i jarvis_approval_admin.
- Aktuellt antal aktiverade jarvis_approval_admin-medlemskap: 0. Ingen ägaridentitet kan därför godkänna via det nya flödet ännu.

## Föreslagen lösning

Migrationen återkallar direkt tabellåtkomst för PUBLIC, anon och authenticated och tar bort endast de kända klientpolicies som tillåter anonyma/inloggade direktvägar. Serverrollens befintliga behörigheter och jarvis_service_all-policies lämnas kvar.

## Avsiktlig säkerhetsgrind

Migrationen kontrollerar FÖRE varje återkallelse att:
1. jarvis_approval_admin-tabellen finns.
2. jarvis_approval_decide-RPC:n finns.
3. minst ett aktiverat ägar-/adminmedlemskap finns.
4. service_role kan köra RPC:n.

I den nuvarande produktionsstatusen är antalet aktiverade medlemskap noll. Migrationen ska därför avbrytas utan ändringar tills en verklig Supabase Auth-användare har verifierats och en behörig administratör har provisionerat medlemskapet. Ingen användare, auth-post eller adminbehörighet skapas av denna migration.

## Driftsättningsplan (kräver separat godkännande)

1. Registrera en riktig ägaridentitet genom det avsedda Supabase Auth-flödet.
2. Verifiera identiteten och provisionera en enda aktiverad rad i jarvis_approval_admin via administrativt, granskat förfarande.
3. Testa jarvis-approval-admin i staging med rätt ägare, fel ägare och saknad JWT.
4. Applicera migrationen först när preflight passerar.
5. Verifiera att anon och authenticated nekas direkt åtkomst till approval_decision och approval_request.
6. Verifiera att serverbaserad ApprovalGate fortsatt kan skapa R2/R3-förfrågningar och att den verifierade ägaren kan godkänna exakt en gång.
7. Kontrollera att revisionsloggen fortsätter registrera beslut och att n8n/äldre klienter inte längre förlitar sig på anon-skrivning.

## Återställning

Återställ inte anon- eller authenticated-skrivning. Om serverflödet misslyckas: stoppa release, behåll direktklientspärren i staging och reparera ägarautentiseringen. En blockerad approval är säkrare än ett publikt godkännandeflöde.

## Teststatus

- Offline statiska kontrakttester tillagda i tests/test_approval_anon_lockdown.py.
- SQL-migrationen är inte applicerad.
- Ingen auth-användare eller adminmedlemskap har skapats.
- Ingen produktionsbehörighet har ändrats.

Status: FÖRBERETT PÅ SEPARAT BRANCH / BLOCKERAT AV 0 AKTIVA ADMINMEDLEMSKAP / EJ DRIFTSATT.
