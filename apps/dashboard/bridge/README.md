# Privat Jarvis-brygga

## Driftsgräns

Detta är en separat köradapter för den befintliga dashboarden i en privat Computer-förhandsvisning. Den är inte en permanent Vercel-backend och ersätter inte Supabase. Computer-kopplingarnas behörighet kan inte exporteras till Vercel.

Autentisering kontrolleras mot befintliga `jarvis-dashboard-api` med `x-jarvis-key`. Klienten håller nyckeln endast i flikens minne. Servern cachar en SHA-256-identifierad lyckad verifiering i högst 20 sekunder, utan att lagra nyckeln.

## Körning

1. Installera `requirements.txt` i en isolerad Python-miljö.
2. Starta `python -m uvicorn server:app --host 0.0.0.0 --port 8765` med Computer-serververktygets credential presets `pplx-connector` och `llm-api:website`. Modellen använder plattformens enhetliga SDK via `model_client.py`, samma verifierade autentiseringsväg som rösten. Direkt Anthropic-SDK saknade autentisering i denna miljö och ersattes.
3. Bygg dashboarden med `VITE_JARVIS_BRIDGE_URL=__PORT_8765__ npm run build`.
4. Förhandsdriftsätt `dist` med Computer, som skriver om portadressen till den privata serverproxyn.
5. Verifiera rätt/fel nyckel, verkligt modellsvar, minst en verklig läskedja och ljuduppspelning efter driftsättning.

För lokal frontendtestning kan bryggadressen vara `http://127.0.0.1:8765`. Ingen autentiserad backend exponeras utan Jarvis-nyckel.

## Kontroll

- `policy.py` är enda tillåtelselistan. Den innehåller inga skriv-, betalnings- eller utskicksverktyg.
- Klienten kan inte ange ett godtyckligt verktyg eller köra SQL/shell.
- Supabase-läsningar begränsas till Jarvis projekt-id.
- Hämtade data behandlas som opålitliga. Modellinstruktioner får inte utöka rättigheter.
- Högst fyra modellvalda läsanrop per fråga, högst fyra relevanta källor efter routning och två samtidiga modelluppdrag.
- Röst är opt-in. Den genereras först när användaren väljer uppspelning eller aktiverar automatisk uppläsning.
- Inga konfigurerade modellbudgetar i Omega-kärnan ändras. Bryggan har anrops-/tokenbegränsningar, men inget verifierat kronbaserat kostnadstak. Kostnad visas därför som ej mätt.
- Katalogstatus är daterad observation. Ansluten betyder inte funktionstestad.
- Nya samtal är sessionsbundna i webbläsarfliken. Auditminnet i bryggan är tillfälligt.
- Frysta integrationer, Prime-workflows, externa meddelanden och betalningar förblir låsta.

## Återställning

Ändringarna ligger på en separat Git-branch. `main`, produktions-Supabase och Vercel har inte ändrats av detta paket. Avsluta bryggservern och återgå till tidigare frontendversion för att återställa en framtida förhandsdriftsättning.
