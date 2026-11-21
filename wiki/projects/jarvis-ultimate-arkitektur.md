---
id: projects/jarvis-ultimate-arkitektur
item_type: wiki_page
semantic_type: project
title: JARVIS Ultimate — modellrådets arkitekturbeslut
description: 'Ett Model Council (Claude Opus 5, GPT-5.6 Sol, Gemini 3.7 Flash) plus en fristående djupforskningsrapport analyserade oberoende hur Jarvis-ekosystemets 20+ kopplade verktyg ska konsolideras och orkestreras. Alla fyra körningar landar i samma kärnlogik: radikal verktygskonsolidering, ÄTA-fångst på Kungsgatan 37 som första prioritet, och ett Approval Center innan någon agent får skriva pengar/avtal/kunddata.'
created_at: '2026-08-28T06:55:00+00:00'
updated_at: '2026-08-28T06:52:00+00:00'
---
# JARVIS Ultimate — modellrådets arkitekturbeslut

Ett Model Council (Claude Opus 5, GPT-5.6 Sol, Gemini 3.7 Flash) plus en fristående djupforskningsrapport analyserade oberoende frågan "utveckla min Jarvis på ditt ultimata AI godmode sätt", med uppdrag att orkestrera Jarvis 20+ kopplade verktyg (Notion, Supabase, Neon, HubSpot, Monday.com, Asana, GitHub, Slack, Stytch, Google Workspace, Microsoft 365, LegalZoom, Quartr, YouTube, m.fl.). Alla fyra oberoende körningar landar i samma kärnlogik trots olika ingångar [cite:1].

## How it works

- **Radikal verktygskonsolidering.** Samtliga fyra körningar rekommenderar att minska från cirka 23 aktiva konton till en kärna på 12–15, exponerade som ett fåtal kapabiliteter i stället för 20+ råa integrationer — fler direktkopplade verktyg sänker mätbart agentens verktygsvalsprecision och ökar attackytan [cite:1].
- **ÄTA-fångst på Kungsgatan 37 är första prioritet**, inte fler AI-lager eller RAG-system. ÄTA-arbeten utgör typiskt 15–25 % av projektkostnaden (443–739 tkr på det 2 954 000 kr-kontraktet), och AB 04 kap. 2 § 6 kräver skriftlig underrättelse utan dröjsmål — missas fönstret förloras rätten till betalning [cite:1].
- **JARVIS Prime är pausat därför att det byggs horisontellt** (lager för lager) utan en verklig användare. Rekommendationen är att bygga en vertikal skiva genom alla 8 lager för EN process (ÄTA-fångst) mot ett generiskt 9-tabellsschema, i stället för att vänta på att alla lager blir klara i tur och ordning [cite:1].
- **Approval Center krävs innan någon skrivbehörighet öppnas.** Pengar, avtal, kundkontakt och publicering får aldrig utföras autonomt av en agent; godkännandelogiken ska vara deterministisk kod, inte en LLM som godkänner sig själv — särskilt eftersom LLM-övervakare visat sig missa farliga handlingar 2–30 gånger oftare i långa kontexter [cite:1].
- **Två olösta meningsskiljaktigheter kräver ett aktivt beslut från Ricky:** (1) vilken Postgres-databas (Supabase eller Neon) som ska vara produktionssanning — 3 av 4 körningar väljer Supabase; (2) vilken plattform (Google Workspace eller Microsoft 365) som ska äga BTF:s mejl/dokument — ingen modell hade faktisk data om vilket system BTF redan använder mest, så en 30-dagars aktivitetsmätning rekommenderas före låsning [cite:1].
- **En specifik teknisk detalj i underlaget (ett påstått hårdkodat JWT i ett namngivet Supabase cron-jobb, från Gemini 3.7 Flash) saknar källhänvisning och kunde inte verifieras** — behandlas som en misstänkt AI-hallucination tills Ricky själv kontrollerar sin Supabase-instans [cite:1].

## Architecture decisions

- **Databas-standardval: Supabase**, med en 48-timmars migrationsdiagnos som avgör om Neon ska väljas i stället. Exakt en produktionsdatabas får finnas — aldrig två parallella sanningar [cite:1].
- **Uppgiftssystem-standardval: Monday.com**, med Asana fryst/exporterad — om inte en snabb kontroll visar att det egna Boost Sparkle Engine/CommandCenter redan täcker byggprojektets arbetsflöde bättre [cite:1].
- **Byggordning:** migrationsåterställning → kanonisk dataryggrad (9 generiska tabeller: entity, project, event, document, chunk, signal, opportunity, decision, approval) → ÄTA-fångstloop på Kungsgatan 37 → Approval Center → Revenue Engine/Svarar.nu-konciergepilot. Inga nya produktionsintegrationer innan migrationsgrinden är passerad [cite:1].
- **Agentorganisation:** behåll Crisis Sentinel ∞:s Conductor-mönster men begränsa till Conductor + högst 4 specialiserade roller (Research, Operations, Revenue, Risk/Verifier) — inte fler autonoma personas [cite:1].

## See also

- [[projects/aktiva-initiativ]] — beslutsloggen för de fyra aktiva initiativen som denna arkitektur ska betjäna
- [[projects/godmode-automation-och-kopplingar]] — de bekräftade kontokopplingarna som konsolideras i denna arkitektur
- [[projects/crisis-sentinel-infinity]] — agentorchestration-arkitekturen som ligger till grund för Conductor + roller-modellen
- [[projects/boost-sparkle-engine]] — kontrollpanelen (lager 8) och den ERP/CRM-plattform som är alternativ till Monday.com
- [[concepts/godmode-driftprotokoll]] — reglerna för kvantifiering och beslutslogg som denna analys följer

## References

[cite:1]: pplx://sessions/485f7652-970e-4e81-b098-3c72dd254f7f
