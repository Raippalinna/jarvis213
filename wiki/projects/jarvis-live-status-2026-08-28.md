---
id: projects/jarvis-live-status-2026-08-28
item_type: wiki_page
semantic_type: project
title: Jarvis skarp statusverifiering 28 aug 2026 — korrigerar tidigare "pausat"-status
description: Direkt inspektion av produktions-Supabase, GitHub, Notion, HubSpot, Monday.com och Slack visade att flera tidigare wiki-antaganden var inaktuella. JARVIS Prime/TITANOS-migrationen är klar (110/110 tabeller), ett Notion-baserat kontrollrum är redan byggt och valt som primär sanningskälla, en verklig säkerhetsläcka hittades och åtgärdades, och HubSpot/Monday.com/Slack är anslutna men fortfarande tomma.
created_at: '2026-08-28T07:10:00+00:00'
updated_at: '2026-08-28T07:07:00+00:00'
---
# Jarvis skarp statusverifiering 28 aug 2026

Efter modellrådets arkitekturbeslut ([[projects/jarvis-ultimate-arkitektur]]) begärde Ricky att faktiskt koppla ihop Jarvis-ekosystemet. En direkt inspektion av produktions-Supabase, GitHub, Notion, HubSpot, Monday.com och Slack via kopplingarna visade att flera tidigare wiki-antaganden var inaktuella [cite:1].

## How it works

- **JARVIS Prime/TITANOS-migrationen är klar, inte pausad.** Produktions-Supabase-projektet `fzmnqvmfilqizzftphbt` innehåller 108 tabeller, 7 migrationsomgångar (`titanos_migration_chunk_01`–`06`) är applicerade, och RLS är aktiverat på samtliga tabeller. Detta korrigerar den tidigare statusen "pausat i väntan på migrationer" i [[projects/aktiva-initiativ]] [cite:1].
- **Ett Notion-baserat "RICKY Ω∞ OS — Jarvis Control Room" är redan byggt och valt som primär sanningskälla** för en 30-dagars testperiod (beslutat 2026-08-24, materialiserat 2026-08-28), med tre databaser: Beslutslogg (kvantifierad, med Kr-effekt/Sannolikhet/DRY_RUN-fält enligt godmode-driftprotokollet), Ekosystem/Initiativ, och Inkomst-radar. En webb-HUD-dashboard är också byggd och delad i en annan tråd [cite:1].
- **En verklig, bekräftad säkerhetsläcka hittades och åtgärdades:** ett `pg_cron`-jobb (`connector-health-15m`, var 15:e minut) skickade en hårdkodad JWT-bearer-token i klartext till en annan, gammal Supabase-databas (`qkwmgvlqqagjozubnrlc`). Jobbet togs bort efter godkännande av Ricky. Detta bekräftar att Gemini 3.7 Flashs fynd i modellrådet (tidigare flaggat som möjlig hallucination) faktiskt var korrekt [cite:1].
- **RLS-policyerna är korrekt utformade** (`auth.uid() = user_id`-mönster) på de granskade tabellerna (companies, chat_messages, aiden_memory, crm_leads) — den kvarstående risken är enbart att `anon`-rollen kan se tabellernas *schema* via GraphQL-introspektion, inte faktisk data, eftersom `auth.uid()` är null för oautentiserade anrop. Detta är en lägre allvarlighetsgrad än ursprungligen befarat, men bör ändå åtgärdas (revoke SELECT från anon) som en enkel härdningsåtgärd [cite:1].
- **HubSpot, Monday.com och Slack är anslutna på kontonivå men strukturellt tomma:** HubSpot-portalen har inte slutfört onboarding (`onboarded: false`), Monday.com har noll boards/favoriter, och ingen Slack-kanal för Jarvis existerar än. "Kopplad" betyder alltså autentiserad, inte utbyggd — den fysiska verktygslagret (CRM, uppgiftstavla, notiskanal) återstår att bygga ut [cite:1].

## Architecture decisions

- **Notion är primär sanningskälla för det operativa kontrollrummet under 30-dagarsperioden**, inte den Perplexity-projektwikin. Perplexity-wikin fortsätter som den djupare, tvärgående kunskapsbasen (arkitektur, entiteter, tekniska beslut) medan Notion hanterar daglig beslutslogg och ekosystemöversikt. Båda bör hållas i synk vid större beslut [cite:1].
- **Nästa konkreta flaskhals är skarp auth/RLS-testning med verkliga användarflöden**, inte fler integrationer — detta är redan identifierat i Notions Beslutslogg och bekräftas av den tekniska granskningen här [cite:1].

## See also

- [[projects/jarvis-ultimate-arkitektur]] — modellrådets arkitekturbeslut som denna verifiering bygger vidare på
- [[projects/aktiva-initiativ]] — beslutsloggen vars JARVIS Prime-status härmed korrigeras
- [[projects/boost-sparkle-engine]] — kontrollpanelen/appen som körs mot detta Supabase-projekt
- [[projects/godmode-automation-och-kopplingar]] — de bekräftade kontokopplingarna, nu verifierade som anslutna men delvis tomma (HubSpot/Monday/Slack)

## References

[cite:1]: pplx://sessions/485f7652-970e-4e81-b098-3c72dd254f7f
