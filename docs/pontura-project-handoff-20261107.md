# Pontura: ChatGPT ↔ befintlig JARVIS – projektavgränsad överlämning

**Datum:** 2026-11-07  
**Status:** FÖRBERETT / EJ ANSLUTET / EJ DRIFTSATT

## Syfte

Koppla **den befintliga** JARVIS i Perplexity Computer och ChatGPT till projektet **Pontura**, utan att skapa en ny Jarvis, ändra globala agentinstruktioner eller importera data från andra projekt. Detta dokument är ett kopplingskontrakt, **inte ett bevis på en aktiv integration**.

## Identifierade resurser

| Funktion | Auktoritativ referens | Åtkomststatus |
| --- | --- | --- |
| Projektfilarea i Perplexity | https://www.perplexity.ai/projects/09dba2a5-72dd-46e6-938f-001e9321c61e | Innehåll, skrivåtkomst och autentiserad inventering **ej verifierade** |
| Perplexity-session om mappkoppling | https://www.perplexity.ai/session/bb159d9e-a197-45d0-9c23-a6d5e8caf102 | Browser blockerad av ExtensionsSettings-policy |
| Pontura privat kontrollrum | https://app.notion.com/p/41166d43c107816d98a4c198ce6f7b57 | Åtkomligt för ChatGPT via Notion-koppling |
| Pontura agentsektion | https://app.notion.com/p/41166d43c107816fae63ceffaff0705f | Projektgräns och status dokumenterade |
| Befintlig JARVIS-kod | https://github.com/rickyraippalinna/jarvis-omega-v2 | GitHub-läsning verifierad; körning av agenten ej verifierad i denna ändring |
| Överlämningskontrakt v1 | docs/chatgpt-jarvis-handoff-v1.md | Befintligt dokument, oförändrat |

## Arkitektur

1. **Perplexity Computer/JARVIS** förblir huvudorkestrator. Den använder Pontura-projektet när dess behörighet och filvy har verifierats.
2. **Notion Pontura** är ett separat privat kontrollrum för källjournal, beslut, status och revisionsspår. Det är *inte* en implicit synk av Perplexity-filer.
3. **ChatGPT** är en specialistklient. Den får bara läsa/skapa projektavgränsade leverabler via redan godkända appar och får aldrig anta att en ChatGPT-konversation automatiskt uppdaterar Perplexity.
4. **GitHub Actions/JARVIS runtime** kan ta emot auktoriserade `repository_dispatch` av typen `jarvis-run`, enligt befintliga `docs/chatgpt-jarvis-handoff-v1.md` och `.github/workflows/jarvis-cloud.yml`. Ingen ny permanent agent eller långlivad åtkomstnyckel införs här.

## Projektavgränsat arbetsobjekt

Varje begäran ska innehålla: `project=pontura`, unikt `request_id`, specifik uppgift, källreferens eller dokumentversion, klassning, begärd åtkomstnivå och resultatstatus. Identitetsuppgiften `origin=chatgpt` är endast en **opålitlig etikett** och får aldrig ge behörighet.

**Illustrativt exempel, EJ skickat:**

```json
{
  "event_type": "jarvis-run",
  "client_payload": {
    "task": "Pontura: inventera endast filnamn och versioner i ett redan auktoriserat projekt; ändra ingenting; rapportera blockerad åtkomst tydligt",
    "tier": "FREE",
    "origin": "chatgpt",
    "request_id": "00000000-0000-4000-8000-000000000001",
    "notion_page_id": "41166d43-c107-816d-98a4-c198ce6f7b57"
  }
}
```

Denna payload har **inte** ett explicit `project`-fält i nuvarande workflow. Om projektflagga behövs i exekvering, inför en separat validerad parameter och tester i en senare PR; lita inte på fritext i `task` för auktorisering. Dispatch kräver godkänd serverautentisering; lämna aldrig GitHub-token, Perplexity-nycklar eller Notion-token i promptar, dokument eller klientkod.

## Acceptanskriterier före status ANSLUTEN

- [ ] Perplexity-projektets faktiska fillista verifierad med legitim autentisering och utan att kringgå skydd.
- [ ] Tillgång för huvud-JARVIS till rätt Pontura-projekt bekräftad. Ingen global workspace- eller kontotäckande rättighet om projektavgränsning fungerar.
- [ ] ChatGPT kan läsa och dokumentera en ofarlig testpost i sin godkända delade källarea, med dokument-ID och versionsspår.
- [ ] En auktoriserad avsändare kan skapa ett ofarligt testjobb med unik `request_id`. Actions-körning, resultat och felstatus verifieras; HTTP 204 ensamt räcker inte.
- [ ] JARVIS kan läsa samma uppgiftsreferens och visa resultatet för Pontura i Perplexity utan att röra andra projekt.
- [ ] Behörighetsförlust, dublett, timeout, tomt resultat och misslyckad körning hanteras och loggas.
- [ ] Kostnadstak, approval-grindar, dry-run och kill switch kontrollerade.

## Nuvarande blockerare och säkerhetsgräns

- Browser till Perplexity-sessionen ger `ExtensionsSettings`-fel. TinyFish-profilen har ännu ingen sparad verifierad inloggning för `perplexity.ai`. En extern profil kräver att kontoinnehavaren slutför legitim inloggning.
- Ingen dator är ansluten till Desktop Commander.
- Perplexitys officiella API-MCP ger sökning/research, inte automatiskt tillgång till privata Computer-sessioner eller projektfiler.
- Dela inte personuppgifter, affärshemligheter, kundregister eller finansiella originalfiler förrän åtkomst, dataskydd och lagringsdestination verifierats.
- Ändra inte andra repon, workflows, hemligheter, databaser eller produktion i detta steg.

## Kontroll och återställning

**Genomfört:** Inventering av existerande GitHub-repo och kontrakt; sammanställning av Ponturas verifierade länkar; dokumentationsändring på separat branch.  
**Ej genomfört:** Perplexity-inloggning, filimport, credential-setup, tvåvägsprov, tester av runtime eller deployment.  
**Återställning:** Stäng PR utan merge och radera feature-branchen vid behov. Inga aktiva systemflöden ändras av dokumentationsfilen.
