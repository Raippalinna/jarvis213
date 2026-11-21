# Jarvis kontrollrum: testomfattning

## Funktioner som ska verifieras

| Område | Test | Förväntat |
|---|---|---|
| Inloggning | Fel nyckel, rätt befintlig nyckel, utloggning | Nekad åtkomst utan rätt nyckel; privat underlag efter inloggning |
| Dashboard | Supabase state | Verkliga tidsstämplar; inga uppdiktade mätvärden |
| Anslutningar | Öppna från skrivfält, sök, välj, avmarkera, välj alla, rensa | Val speglas i skrivfältet; låsta tjänster förblir låsta |
| AI-dialog | Allmän fråga och Supabase-fråga | Verkligt modellsvar; läsanrop redovisas |
| Sidoeffekter | Försök skicka mejl med manipulerade verktygsnamn | Serverns tillåtelselista nekar |
| Avbrott | Avbryt pågående svar | UI återhämtas; beskriver att redan startad läsning kan fortsätta |
| Personlighet | Varm +, Gnista, Fokus | Tonval går till modell och röst |
| Röst | Genererad MP3, uppspelning, stopp | Ljud framtaget; bubblan följer faktisk ljudnivå vid uppspelning |
| Mikrofon | Saknat stöd, diktering | Tydlig reserv; transkript skickas inte automatiskt |
| Insyn | Expanderad läslogg, aktivitet, minne | Tjänst och verktyg redovisas, gammalt backendminne särskiljs |
| Tillgänglighet | Tangentbord, Escape, fokusfälla, reducerad rörelse | Användbar utan mus; rörelse kan begränsas |
| Responsivt | 1440×1000 och 375×812 | Ingen horisontell överrinning; skrivfält och navigation åtkomliga |
| Ljust/mörkt | Båda teman | Text och kontrollernas etiketter läsbara |

## Gränser

- Computer-bryggan är en privat förhandsdrift, inte permanent Vercel-backend.
- Nya samtal lagras i fliken. Supabase-originalet ändras inte.
- Inga schemalagda jobb eller utskick aktiveras.
- Arbetslägen är frågemallar, inte ett påstående att Computer-skills importerats.
- Mikrofon på användarens telefon och genväg i Windows kräver test på en online-enhet.
- Alla läsadaptrar kan inte anses funktionstestade enbart av att katalogen visar dem.
