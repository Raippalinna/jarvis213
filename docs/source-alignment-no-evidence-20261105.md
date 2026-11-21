# Strikt källkontroll – implementation och verifieringsgräns

## Integration
Befintliga reflect() gör redan grounding.update(audit_source_titles(...))
före kvalitetstaket. Integrationen ligger därför i source_references.py;
Supervisor behöver inte skrivas om eller ersättas från en trunkerad läsning.

JARVIS_STRICT_SOURCE_ALIGNMENT är avstängd som standard. Endast exakt 1
aktiverar den. Ingen miljövariabel eller produktionskonfiguration ändras här.
När flaggan saknas är returkontraktet oförändrat och provenance importeras inte.
I strikt läge bedöms varje punkt av provenance. Otillräcklig kontext, saknat
belägg, felande kontroll och överskriden inmatningsgräns räknas som ostödda.
reflect():s befintliga tak min(quality_score, 0.5) används; ingen höjning görs.

## Mått
I strikt läge är sourced/unsourced antal punkter med/utan användbart
referensstöd. items = sourced + unsourced. De tidigare formatmåtten finns
som format_sourced/format_unsourced. Titelräknarna är oförändrade.
source_alignment innehåller enbart statusar, spärrläge och truth_verified=False;
inte källtext, svarets innehåll eller råa felmeddelanden.
En titelmatch verifierar aldrig sanningen i ett faktapåstående.
Ett ärligt besked om saknade data är inte källstöd och får också kvalitetstak.

## Genomförda lokala tester
28 nya testfall passerade i isolerad arbetskopia. Källmodulerna hämtades från
grenen; originalen verifierades med Git-blob SHA före ändring:
- source_references.py: a6da1f12f3dee84d97fecf14ed9400b5505be566
- provenance.py: ab438916df7742b695940e08b584603f7b5fb320
Syntaxkontroll av ändrad modul och testfil passerade.
Testerna kör det oförändrade reflect-utdraget via AST, riktiga audit/provenance,
stubbad grundpoäng/formatsignal och helt avstängt minneslager. Paketimport,
LangGraph-körning och hela reposviten är inte verifierade lokalt.
Testat: default/avstängd flagga, matchad/falsk/saknad källa, blandade belägg,
tom kontext, kontrollfel, låg grundpoäng, tomt svar, felplatshållare,
icke-källberoende roll, syntetisk fallback-metadata, avbrott via CancelledError,
indatagräns samt frånvaro av känslig text i kontrollmetadata.
Den verkliga provider-fallbacken är inte körd av dessa nya tester.

## CI och återstående gränser
Befintliga jarvis-code-quality.yml kör hela Python-sviten med nätverk spärrat,
JavaScript-tester och dashboardbygge vid PR mot main. Inget nytt workflow behövs.
Full CI måste verifieras på slutlig PR-head efter sparning och PR-skapande.
Ingen merge, deployment, live-modell, Supabase-skrivning eller Notion-leverans
har utförts. Befintlig minnespersistens ändras inte; testerna använder ingen
produktionsdatabas. Kill switch, DRY_RUN, Approval Center, budget och routing
är oförändrade. Produktionsaktivering kräver separat godkännande och driftprov.

## Återställning
Revert:a integrationscommiten för source_references.py och den nya testfilen.
Tidigare no_evidence-rättning kan ligga kvar. Ingen migration behövs.
Status: FÖRBERETT + TESTAT LOKALT. Sparning och CI bekräftas separat.
