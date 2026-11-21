# Foundation-rättning, 27 september 2026

Bygger på PR #5. Sex typade specialistkontrakt används av supervisorn för
avgränsade utkast; de är inte sex självständiga verkställande verktygsagenter.
Frugality finns kvar. Providerkatalog och budgettrösklar är oförändrade.

## Ändrat

- Flerturnshistorik med rollfiltrering och gränser följer specialistens anrop.
- Tomma svar och undantag är fel, inte lyckade svar. Råa felkroppar loggas inte.
- Runtime-fallback kontrollerar modell, kvalitetsgolv, uppskattat kostnadstak och träningspolicy.
- Actions-indata behandlas som JSON-data, inte som interpolerad shellkod.
- Exit 1 = körningsfel, 2 = väntande godkännande, 3 = minnes-/auditfel, 4 = leveransfel.
- Notion-larmsink använder PATCH; audit actor_type är agent.
- Supervisorn stoppar före skrivningar/modellanrop om autonomiflaggan inte är uttryckligen sann, eller om audit-loggen inte kan sparas.
- Godkännandebegäran returneras endast efter bekräftad audit. Delvis skapade rader kan kvarstå tills atomisk RPC införs; de får inte utlösa modell eller notifiering.
- Genererade minnen märks overifierade; felsvar sparas inte som vanliga konversationer.
- Månadsaudit har PYTHONPATH, döljer inte stegfel och skiljer saknade data från noll.

## Kvar före produktionsgodkännande

Skrivskyddat GitHub-förtest 27 september: `COMET_API_KEY` finns; backend-nyckelns
claim är `anon`; autonomi och minnesläsning ger HTTP 401. Audit kan läsas men
skrivrättigheter är inte provade. Offline-testjobbet lyckas, backend-jobbet stoppar
med exit 1. Nyckeln behöver ersättas säkert före fortsatt driftprov.
[Verifierad testkörning](https://github.com/rickyraippalinna/jarvis-omega-v2/actions/runs/36285798906).
Efter diagnosen begränsades backend-förtestet till manuell `workflow_dispatch`.
Push- och PR-jobb kör enbart nyckelfria offlinetester.

Backend-nyckelns verkliga rättigheter, kill-switch i fristående äldre runtime-ingångar,
tenant-filtrering även i minnes-RPC, idempotent minnesskrivning, säker
autentiserad återupptagning efter godkännande och verifierad mottagarleverans.
Nuvarande godkännandegrind avslutar turen; den genomför inte ett beslut.
Kvalitetsvärdet är en formatheuristik och bevisar inte innehållets sanningshalt.
Kostnad baseras på katalogestimat, inte leverantörsfaktura. Månadsaudit stoppar
vid 1000 rader hellre än att presentera en ofullständig summering som fullständig.

## Test

```sh
PYTHONPATH=src:. python -m pytest tests -q
```

Ingen notifiering eller betald modellkörning behövs för denna testsvit.
Ingen merge eller produktionsmigration utförs av denna gren.
