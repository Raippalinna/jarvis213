# Perplexity Computer – manuell privat överlämning (2026-11-10)

## Syfte
Gör en redan befintlig privat Perplexity Computer-uppgift, artefakt eller session åtkomlig från Jarvis Ω∞ Dashboard utan Lovable-credits och utan att skapa en API-nyckel eller imitera Perplexity-inloggning.

## Funktion
1. Öppna Dashboard → System efter befintlig Jarvis-inloggning.
2. Klistra in din egen fullständiga HTTPS-länk av typen `https://www.perplexity.ai/computer/tasks/<uuid>`, `https://www.perplexity.ai/computer/a/<uuid>` eller `https://www.perplexity.ai/session/<uuid>`.
3. Den klientlokala valideringen accepterar endast `perplexity.ai` eller `www.perplexity.ai`, endast de tre uttryckligen tillåtna sökvägsformaten och inga query/fragment/credentials.
4. Välj **Öppna i Perplexity**. Browsern öppnar en separat flik. Perplexity ansvarar för den faktiska sessionen och åtkomstkontrollen.
5. Om Perplexity kräver inloggning behöver kontoinnehavaren själv logga in där. Detta kontrollrum läser inte privat Perplexity-innehåll, och skickar inte länken till egen backend.

## Säkra gränser
- Ingen `localStorage`, serverpost, loggning eller permanent lagring av privat Computer-länk; fältet hålls endast i React-komponentens minne.
- Ingen hemlighet, credential, iframe, API-anrop, proxy, webbskrapning eller nätverkstest har tillförts.
- En giltig länk betyder **endast formatvaliderad**, inte nåbar/autentiserad/körtestad.
- Inga förändringar i Approval Center, `DRY_RUN`, kill switch, Supabase eller arbetsflöden.
- Ingen deploy/merge eller Perplexity Computer-kontoanslutning.

## Tester och verifiering
`node --test tests/test_perplexity_computer_url.mjs` testar produktionsvalideraren med Node 22:s inbyggda TypeScript-stripper, utan nätverk och utan secrets. Ett lokalt förtest gav 2/2 godkända tester. Tidigare GitHub CI på PR-head `024dce94` var grön; dessa nya ändringar kräver en separat CI-kontroll på ny commit. Faktisk Perplexity-inloggning och session behöver verifieras separat.

## Återställning
Stäng pull requesten utan merge. Inga databasändringar eller externa tjänster behöver återställas.

## Begränsning
Den privata Perplexity Computer-uppgiften är fortfarande oåtkomlig utan auktoriserad Perplexity-session. Denna kod underlättar öppning av den uppgiften men kör eller slutför inte uppgiften automatiskt.
