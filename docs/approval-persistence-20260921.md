# Approval Center: korrigerat lagringskvitto

Historisk kontrollpunkt för commit `3e868b7`. Lagringsdelen har därefter ersatts
av den atomiska kandidaten i
[uppföljningen 22 september](https://github.com/rickyraippalinna/jarvis-omega-v2/blob/improvement/jarvis-reliability-20260920/docs/approval-atomic-20260922.md).
Testantal och kvarlistan nedan beskriver den tidigare kontrollpunkten, inte den
senaste kodversionen.

## Omfattning och status

Fortsättning på `improvement/jarvis-reliability-20260920`, inte en ny dashboard.
Kodkandidaten rättar godkännandelagring och statusrapportering. Main och
produktionsdatabasen ändras inte av denna commit.

## Verifierade observationer

- GitHubs metadata för `SUPABASE_SERVICE_ROLE_KEY` visade fortfarande ändringsdatum
  2026-08-29T13:19:41Z. Nyckeln för rätt Supabase-projekt och rollen `service_role`
  fördes till rätt GitHub-fält, men sparningen stannade vid GitHubs
  ”Confirm access”. Ingen lyckad nyckeluppdatering är därmed verifierad
  ([GitHub-inställningen](https://github.com/rickyraippalinna/jarvis-omega-v2/settings/secrets/actions/SUPABASE_SERVICE_ROLE_KEY)).
- Databasens CHECK-regel kräver `actor_type IN ('human','system','agent')`;
  äldre kod skickade `jarvis_agent`. Vid läsningen fanns noll approval_decision-rader
  ([Supabase-projektet](https://supabase.com/dashboard/project/fzmnqvmfilqizzftphbt)).
- Databasen hade dessutom fyra klientpolicyer på approval_decision, en på
  approval_request och en på approval_audit_log. Den anonyma UPDATE-policyn
  begränsade bara tenant, inte status eller godkännare. Detta är inte en säker
  mänsklig godkännandegrind
  ([Supabase-projektet](https://supabase.com/dashboard/project/fzmnqvmfilqizzftphbt)).

## Ändrat i kandidaten

- `actor_type='agent'` och explicit aktörs-ID.
- Sparat kvitto kräver giltigt UUID och lyckade beslut-, begäran- och audit-svar.
- Fel vid någon skrivning ger `approval_persistence_failed`, inte sparat vänteläge.
- Flödet haltar även vid lagringsfel; ingen modell eller affärsåtgärd startas.
- Begäran gäller granskning (`create`), inte exekvering, och får 24 timmars
  utgångstid som granskningsmetadata. Ingen exekverare finns som kan använda den.
- Inga påhittade 50-procentiga sannolikheter, kapitalbehov från tokenkostnader
  eller slutsatser om reversibilitet från nyckelord.
- Halt ger ingen uppmätt kvalitetspoäng. Texten lovar inte automatisk återupptagning.
- Cloud-körningar får ett riktigt sessions-ID om anroparen inte anger ett.
- Förberedd SQL tar bort exakt de sex observerade klientpolicyerna, behåller
  service-role-åtkomst och rader. Driftkontroll stoppar vid oväntade kvarvarande
  klientpolicyer. SQL-filen har inte körts i produktion.

## Test och återställning

Kör från repositoryroten:

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -v
git diff --check
```

81 tester passerade lokalt, inklusive 11 nya tester för godkännandeflödet.
Testerna använder syntetiska uppgifter och mockade nätverksanrop. De täcker
lyckat kvitto, fel vid samtliga tre skrivningar, tomma/felaktiga svar, HTTPS,
stoppat flöde, sessions-ID, uteblivna modell/minnesanrop och redigerade felloggar.
Testerna verifierar inte produktions-RLS eller faktiska databastransaktioner.

## Återkommande uppgifter

De tre Computer-uppgifterna kopplingskontroll, foto/OCR-intag och veckobriefing
togs bort efter upprepade fel om betalning/kredit. Inga betalningsinställningar
ändrades. Definitionerna före avstängning sparas i
`schedules-disabled-20260921.json` för en uttryckligen begärd återställning.
GitHub Actions-scheman är separata och har inte stängts av.

Återställ kod genom att reverta denna commit på utvecklingsgrenen.
Den separata SQL-återställningen dokumenterar exakt observerade gamla policyer,
men återöppnar säkerhetsluckan och får inte användas som automatisk fallback.

## Kvar före skarp godkännandekedja

1. Användaren slutför GitHubs identitetskontroll; läs därefter tillbaka metadata.
2. Godkänn och tillämpa den exakta säkerhetsändringen separat. En dashboard som
   idag förlitar sig på anonym direktåtkomst kommer avsiktligt att förlora den.
3. Ersätt de tre separata skrivningarna med en atomisk, idempotent serveroperation.
   Ett fel kan fortfarande lämna delvis sparade pending-rader; gör inte blind retry.
4. Bygg autentiserad mänsklig granskning och typade åtgärder bundna till exakt
   mottagare, payload, utgångstid och engångsexekvering. Ett radstatusbyte räcker inte.
5. Granska hela utvecklingsgrenens tidigare öppna releasekrav innan main ändras.
6. Gör en uttryckligen godkänd syntetisk driftkontroll utan kunddata, betalning,
   meddelande till tredje part eller ändrad kill switch.

RLS-fel bevisar inte ensamt att en nyckel har fel innehåll. Den äldre klientens
`return=representation` och tabellpolicyer måste också granskas. Ett fungerande
nyckelbyte löser inte automatiskt audit-CHECK-felet eller de öppna behörigheterna.
