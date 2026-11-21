---
id: projects/boost-sparkle-engine
item_type: wiki_page
semantic_type: project
title: Boost Sparkle Engine (JARVIS Construction CRM)
description: Rickys full-stack construction ERP/CRM-applikation byggd på Lovable och underhöllen på GitHub som privat repo (Lovable project 15644bfb-da28-447a-bc94-15856f51daf8). Den implementerar ett komplett bygg-ERP med Kontrollrum, CommandCenter, AI...
created_at: '2026-08-27T22:44:00+00:00'
updated_at: '2026-08-28T04:41:00+00:00'
---
# Boost Sparkle Engine (JARVIS Construction CRM)

Rickys full-stack construction ERP/CRM-applikation byggd på Lovable och underhöllen på GitHub som privat repo (Lovable project 15644bfb-da28-447a-bc94-15856f51daf8). Den implementerar ett komplett bygg-ERP med Kontrollrum, CommandCenter, AI-assistent och ett brett CRM-modulsystem [cite:1].

## How it works

Applikationen samlar bygg- och entreprenadverksamhet i ett system: ByggplatsHub, Personalliggare med QR-check-in, KMA (kvalitet/miljö/arbetsmiljö), Dagbok, Leverantörer, Maskiner, Transport, Kontrollrum och CommandCenter, samt AI-assistenten "Aiden" [cite:1]. CRM-modulerna täcker hela affärsflödet:

- **Affärsutveckling & anbud** — CRMJobProspecting, CRMBidGenerator, CRMCalculations/CRMCalculationEdit, CRMTenderMonitor, CRMWinAnalysis, CRMQuickCalc, CRMMarketAnalysis, CRMOrderstock [cite:1].
- **Projektledning** — CRMProjectHub, CRMDrawings, CRMDocuments, CRMGPSMap, CRMTidsplan, CRMKontrollplan, CRMBIMViewer [cite:1].
- **Ekonomi & avtal** — CRMBetalplan/CRMPaymentPlan, CRMGuarantees, CRMProcurement, CRMBidEdit [cite:1].
- **Kommunikation & försäljning** — CRMCommunicationHub, CRMProactiveSales [cite:1].

## Architecture decisions

Originalets Lovable-Supabase-databas (projekt-prefix `qkwmgvlqqagjozubnrlc`) blev pausad/oåtkomlig utan känt lösenord. Ricky beslutade att migrera hela schemat till ett nytt, eget Supabase-projekt (`fzmnqvmfilqizzftphbt`, org "rickyraippalinna's Org") istället för att försöka återfå Lovable-åtkomsten — detta är nu den aktiva produktionsdatabasen för appen.

- Schemat migrerades från 72 originalmigrationsfiler, applicerade i 7 delar. Verifierat via exakt set-diff mot appens TypeScript-typer (`types.ts`): 110/110 tabeller matchar, alla med RLS aktiverat.
- Appens `.env` pekar nu på det nya projektet; koden är ombyggd och omdeployad med backend live.
- Routern i `App.tsx` använder `HashRouter` (inte `BrowserRouter`) eftersom appen körs bakom en dynamisk subpath i förhandsvisningsmiljön — annars ger direktnavigering till underroutar 404. Två kvarstående `window.location.href = "/auth"`-anrop (i `DOUPage.tsx`/`ModuleE.tsx`) kringgår denna router och bör bytas till `navigate("/auth")`.
- **Känd säkerhetsrisk att åtgärda:** en pg_cron-jobb (`connector-health-15m`) och en trigger-funktion i schemat anropar fortfarande den gamla, oåtkomliga Lovable-databasens edge function med en hårdkodad anon-JWT i klartext (kom med i originalmigrationen, ej agent-introducerad). Bör städas bort och den gamla nyckeln roteras/spärras.

## See also

- [[entities/ricky-raippalinna]] — byggen och ägare
- [[concepts/godmode-driftprotokoll]] — operativt ramverk som styr hur systemet används strategiskt
- [[projects/crisis-sentinel-infinity]] — relaterad AI-orchestration-arkitektur

## References

[cite:1]: https://github.com/rickyraippalinna/boost-sparkle-engine
