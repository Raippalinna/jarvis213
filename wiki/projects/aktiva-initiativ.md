---
id: projects/aktiva-initiativ
item_type: wiki_page
semantic_type: project
title: Aktiva initiativ i Jarvis-ekosystemet
description: 'Jarvis-ekosystemet driver just nu fyra parallella spår: ett aktivt betalande byggprojekt, två oprövade digitala affärsidéer, och ett pågående systembygge av JARVIS Prime självt. Detta är beslutsloggen som den veckovisa ekosystem-briefingen...'
created_at: '2026-08-27T22:39:00+00:00'
updated_at: '2026-08-28T10:21:00+00:00'
---
# Aktiva initiativ i Jarvis-ekosystemet

Jarvis-ekosystemet driver just nu fyra parallella spår: ett aktivt betalande byggprojekt, två oprövade digitala affärsidéer, och ett pågående systembygge av JARVIS Prime självt. Detta är beslutsloggen som den veckovisa ekosystem-briefingen läser för statusuppdateringar [cite:1].

## How it works

- **Fasadprojekt Kungsgatan 37 (Bra Tak och Fasad / BTF Group)** — Detaljerad kalkyl för rivning av befintlig fasad och ny kassettfasad (leverantör Devex AB), med fönsterbyte som option (leverantör ST24 AB, 193 fönster) [cite:2]. Huvudentreprenaden är kalkylerad till 2 954 000 kr exkl. moms, inklusive ställning/bygghiss över en 14-veckors hyresperiod, byggetablering och maskinhyra (185 100 kr), och en riskpost på 6 % [cite:2]. Nästa steg: stämma av kalendertid mot hyresperioden och vänta in Devex slutgiltiga å-priser för kassetterna [cite:2].
- **Svarar.nu — AI-receptionist för hantverkare** — Affärsidé: en AI som besvarar missade samtal dygnet runt åt svenska hantverksföretag (elektriker, VVS, låssmed, takläggare, bilverkstad), kvalificerar kunden, bokar jobbet och skickar offertunderlag automatiskt, med betalning kopplad till mätbart skapat värde [cite:3]. Status: konceptuellt validerad idé, ej byggd eller lanserad än [cite:3].
- **Finans-micro-SaaS** — Affärsidé: kombinerar finansiella rapporter, YouTube-trender, automatiserad publicering och affiliate-leadfångst i en micro-SaaS [cite:1]. Status: konceptuellt skede, ej byggd eller lanserad än [cite:1].
- **JARVIS Prime-systembygge** — Infrastrukturlager i testmiljö: gemensam datamodell, källspårad kunskapsbas, minne, mönsteranalys, opportunity engine, revenue engine, approval center och kontrollpanel, med krav på fungerande implementation, ingen extern påverkan och rapportering per lager (vad som byggdes, filer, tester, kostnad, fel, nästa steg) [cite:4]. **Uppdaterad status (28 aug 2026):** migrationen är klar (110/110 tabeller matchade i Supabase-projektet fzmnqvmfilqizzftphbt), backend live i förhandsvisning — den tidigare "pausat"-statusen är inaktuell. Kvarstående flaskhals är skarp auth/RLS-testning med verkliga användarflöden innan produktionsanvändning [cite:5].

## Architecture decisions

- **Konstruktion som första kassaflödeskälla** — Fasadprojektet prioriteras som det enda initiativet med bekräftat kassaflöde just nu; de digitala affärsidéerna (Svarar.nu, finans-micro-SaaS) är ovaliderade och ska inte konkurrera om kapital eller tid förrän de har en första betalande kund [cite:1].
- **JARVIS Prime byggs lagervis** — Systembygget görs medvetet i separata, testbara lager (datamodell → kunskapsbas → minne → mönsteranalys → opportunity engine → revenue engine → approval center → kontrollpanel) snarare än som en monolit, för att kunna verifiera varje steg innan nästa påbörjas [cite:4].
- **Testbudget höjd till 2 000 kr per initiativ (28 aug 2026)** — Ricky beslutade att höja testbudgeten till 2 000 kr vardera (totalt 6 000 kr) för Svarar.nu, finans-micro-SaaS och JARVIS Prime-systembygget. Beslutet avviker medvetet från principen "konstruktion som första kassaflödeskälla" ovan, som annars säger att de digitala initiativen inte ska konkurrera om kapital förrän en första betalande kund finns; ingen betal- eller annonsplattform var kopplad vid beslutstillfället (Google Ads frånkopplad), så beloppet är en avsatt testram snarare än en genomförd utbetalning [cite:6].

## See also

- [[projects/fasadprojekt-kungsgatan-37]] — detaljerad kalkyl för Kungsgatan 37-fasaden
- [[projects/boost-sparkle-engine]] — construction ERP/CRM som relaterar till JARVIS Prime-bygget
- [[projects/perplexity-brain-spaces-setup]] — grundstrukturen som denna beslutslogg är en del av
- [[concepts/godmode-driftprotokoll]] — reglerna för hur möjligheter i detta initiativ kvantifieras
- [[projects/godmode-automation-och-kopplingar]] — briefingen som rapporterar status på dessa initiativ varje vecka

## References

[cite:1]: pplx://sessions/46ef5df6-30f2-44f1-b310-2c1e5a677999
[cite:2]: pplx://sessions/4baac41e-5a3b-455e-97b7-cccc41f0e8e5
[cite:3]: pplx://sessions/922168cc-edf0-4e27-8a5e-e023143aaf45
[cite:4]: pplx://sessions/c0452022-43f0-45ef-93d2-0e038ac74bf1
[cite:5]: pplx://sessions/485f7652-970e-4e81-b098-3c72dd254f7f
[cite:6]: pplx://sessions/a34bd0a2-c037-4f7c-96a8-06196dad5063
