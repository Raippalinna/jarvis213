# ChatGPT ↔ JARVIS (Perplexity Computer): säker överlämning v1

## Ägarskap och gränser
- **JARVIS i Perplexity Computer är huvudorkestrator.** ChatGPT är en valfri specialistklient som kan lämna förslag, kodpatchar eller analys för JARVIS granskning.
- Denna ändring **installerar inte** ChatGPT som Perplexity-plugin, öppnar inte en Perplexity-session och aktiverar ingen produktionsintegration. Den förbereder ett verifierbart kontrakt i JARVIS befintliga GitHub-runtime.
- Använd befintligt GitHub Actions `repository_dispatch` av typen `jarvis-run`. Det kräver behörig klient och befintliga GitHub-secrets. **Inga personliga PAT eller Supabase-secrets får anges i ChatGPT-konversationer eller klientkod.**
- Körningar från ChatGPT får aldrig kringgå befintliga Approval Center-grindar, DRY_RUN, kill switch eller kostnadsgränser.

## Jobbkontrakt
Handoff-sändare med redan godkänd server-till-server-auth får göra följande `repository_dispatch` till `rickyraippalinna/jarvis-omega-v2`:

```json
{
  "event_type": "jarvis-run",
  "client_payload": {
    "task": "Granska det bifogade kodförslaget utan att utföra deployment",
    "tier": "LOW",
    "origin": "chatgpt",
    "request_id": "b0d2e4e0-5d41-4b8c-9321-cb1755e8a690"
  }
}
```

`task` krävs (1–8000 tecken); `tier` är FREE, LOW, MED eller HIGH. `request_id` och `chat_id` måste vara giltiga UUID om de skickas. `origin` är **en opålitlig avsändaruppgift**, aldrig en autentiserad identitet. `notion_page_id` stöds fortfarande om ett redan auktoriserat arbetsflöde begär loggning. Inga externa utskick ska läggas till av denna integration.

GitHub Actions startar `scripts/resolve_jarvis_inputs.py` med fält i miljövariabler, inte med okontrollerad text inuti shellscript. Resultaten inkluderar `request_id`, `origin_claim` och `run_url` i `result.json`, vilket möjliggör spårning av ett visst överlämnat jobb. En accepterad dispatch (HTTP 204) är **inte** ett färdigt eller korrekt AI-resultat; kontrollera Actions-körningens faktiska status och resultatfilen.

## Föreslagen samarbetsmodell
1. Ricky ger uppdrag till huvud-Jarvis i Perplexity.
2. Jarvis kan delegera en begränsad deluppgift till ChatGPT via sitt tillåtna arbetsflöde eller versionsstyrd GitHub-handoff. ChatGPT redovisar källor, osäkerhet, testresultat och eventuella kodändringar.
3. Jarvis granskar återlämnat underlag, matchar `request_id`, upprätthåller godkännandekrav och rapporterar den verifierade statusen.
4. En ändring på annan branch är endast **SPARAD**, inte automatiskt MERGAD, DRIFTSATT eller VERIFIERAD I DRIFT.

## Vad återstår för att koppla direkt i Perplexity
- Bekräfta att Perplexity Computer har ett godkänt verktyg/connector för att skapa och läsa just dessa handoff-ärenden.
- Konfigurera serverbehörig sändare med sekretess- och åtkomstkontroll, utan att exponera PAT på klienten.
- Verifiera ett ofarligt provjobb och återläsning av samma `request_id` och Actions-status i båda riktningar.
- Etablera autentiserat ursprung på mottagarsidan. `origin_claim=chatgpt` räcker **inte** för att bevisa avsändare.
- Driftsätt inte ändringarna förrän Ricky har godkänt sammanslagning och eventuell miljökonfiguration.

## Tester och återställning
Kör `python -m unittest discover -s tests -p 'test_jarvis_input_resolver.py' -v` och `python -m pytest tests -q` samt granska GitHub CI:s resultat.

Rollback: stäng ändringsförslaget utan merge eller återställ dess commits efter särskilt godkännande. Ändrar inga databaser, secrets, aktiva scheman eller Perplexity-kontoinställningar.
