# Förmånsagent — isolerad bevakning och HTTPS-adapter

Status: FÖRBERETT och TESTAT LOKALT, inte driftsatt.

## Implementerat
- benefits.py hittar obekräftade kampanjrelaterade textstycken, deduplicerar, hanterar fel och avbrott.
- benefits_http.py läser endast publik HTTPS på uttryckligen tillåtna värdar och port 443.
- DNS-adresser kontrolleras före anslutning; privata, reserverade och multicast-adresser nekas. Den kontrollerade IP-adressen används direkt med TLS-kontroll mot ursprungligt värdnamn.
- Inga redirects, cookies, nycklar, komprimerade svar eller kontoskrivningar.
- Svarsstorlek och socket-timeout begränsas; deadline kontrolleras mellan läsningar. DNS-upplösning har ingen separat hård tidsgräns: driftvärden måste även ha en övergripande timeout.
- Text behandlas som obetrodd data, aldrig instruktioner. Rendera resultat som text, inte rå HTML.
- Fynd räknas inte som verifierade erbjudanden eller realiserade besparingar.

## Teststatus
Första modulens 16 tester passerade isolerat före första commit. HTTPS-adapterns 19 tester passerade isolerat med simulerat nätverk. Ingen sammanhängande körning av hela projektets testsvit eller verklig nätverkshämtning har verifierats. Inga hemligheter behövs i testerna.

## Återstår före kontinuerlig drift
1. Granskade riktiga källor, konfiguration, rate limiting och driftadapter som kopplar scan till fetch_public_html.
2. Varaktig fyndhistorik enligt projektets Supabase-regler.
3. Schemaläggning med kill switch, DRY_RUN och autonomispärr.
4. Leverantörsspecifik verifiering av villkor, behörighet och datum.
5. Approval Center med godkännande bundet till exakt konto och åtgärd.
6. Inlösenadaptrar och verifiering av faktiskt tilldelade krediter.
7. Hela projektets tester, granskning och PR före driftsättning.

Befintliga körvägar, ApprovalGate, budget, routing, produktionsdata och workflows är oförändrade. Återställning: återställ denna feature-branchs commits; ingen datamigrering har gjorts.
