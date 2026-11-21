---
name: jarvis-konfigurationskontroll
description: "Kontrollera och förbättra Jarvis instruktioner i Perplexitys konto-, minnes- och projektinställningar utan avklippt text eller fel scope. Använd vid prompt- och inställningsoptimering för Jarvis. Inte för allmän kodutveckling, connector-hälsokontroll, byggkalkyler eller en vanlig statusfråga."
metadata:
  version: "1.0"
---

# Jarvis konfigurationskontroll

Utgå från en observerad brist, inte önskan att lägga alla skills överallt. Personliga skills är tillgängliga i projekt; tom projektlista betyder inte att de saknas.

1. Läs de aktuella fälten som ska ändras. Skilj personliga instruktioner, Brain-instruktioner, Jarvis projektinstruktioner och projektsammanfattning. Läs inte privata meddelanden för en inställningsändring.
2. Bevara originaltext, mål och lästid. Kontrollera gränser i dagens UI. Den 22 september 2026 observerades 1 500, 1 500, 8 000 respektive 2 000 UTF-16-enheter. Dessa är daterade observationer, inte eviga gränser.
3. Ändra minsta nödvändiga text. Kontot styr generell samarbetsstil, Brain styr varaktigt minne, projektet styr Jarvis regler och sammanfattningen visar aktuellt läge. Duplicera inte hela samma prompt i flera fält. Kopiera inte BTF-skills till Jarvis bara för att fylla en lista.
4. För versionshanterade kandidater, kontrollera befintlig gren och `docs/perplexity/README.md` i `rickyraippalinna/jarvis-omega-v2`. Om paketet finns: kör `python scripts/check_perplexity_config.py` och granska differensen. Om det saknas: verifiera fältlängder separat; påstå inte att testet körts.
5. Spara endast inom godkänd omfattning och gällande bekräftelsekrav. Ändra inte modellabonnemang, behörigheter, kill switch eller produktionsdrift som del av en promptreparation. En installerad skill är inte en körande automation.
6. Öppna sparad inställning på nytt och jämför hela texten. Redovisa mål, ändring, verifiering och blockerare. Skilj fil sparad, UI sparat och observerat beteende.

Klart: berörda fält ryms utan avklippning, original finns för återställning och varje sparpåstående har återläsning. Längdkontroll bevisar inte bättre resonemang. Kör beteendeproven i paketets README endast när faktisk promptkvalitet ska bedömas; registrera annars dem som EJ KÖRDA.

## Triggerprov

- ”Optimera Perplexitys instruktioner för Jarvis” och ”Jarvis-prompten klipps av i inställningar” hör hit.
- ”Kontrollera alla connectors” hör till connector-healthcheck, inte hit.
- ”Ge kort status” ska inte starta konfigurationsarbete.
