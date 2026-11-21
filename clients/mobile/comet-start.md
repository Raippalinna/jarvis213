# Comet-start för Jarvis

Status: FÖRBERETT, inte installerat eller testat i Comets gränssnitt. Den här
prompten förbereder ett uppdrag i befintligt Jarvis, men startar det inte.

## Varför denna startväg

Comet-genvägar är återanvändbara instruktioner som kan öppnas med `/`; de körs
inte bara genom att väljas, utan först när frågan skickas
([Comets instruktioner](https://www.perplexity.ai/help-center/en/articles/11897890-comet-shortcuts)).
Detta bevisar inte åtkomst till Computer-vaulten eller möjlighet att göra
autentiserade API-anrop från en genväg, och den förberedda prompten antar ingen sådan åtkomst.

Den förberedda vägen använder därför användarens inloggade GitHub-formulär.
Ingen endpointnyckel, PAT eller HF-token ska finnas i genväg, URL, bokmärke,
clipboard, webbläsarlagring eller chatt.

## Prompt att granska och spara senare

Avsett namn: `jarvis`. Om en sådan genväg redan finns, granska dess nuvarande
innehåll före en eventuell uppdatering; skapa inte en konkurrerande kopia.

```text
Förbered ett uppdrag i Rickys befintliga Jarvis. Starta det inte.

1. Använd bara uppdragstexten jag uttryckligen lämnar efter genvägen.
   Hämta inte flikar, e-post, dokument eller kontouppgifter automatiskt.
   Om uppdragstext saknas, fråga efter den.

2. Bekräfta att målet är det privata GitHub-repot
   rickyraippalinna/jarvis-omega-v2, arbetsflödet JARVIS Cloud API
   (.github/workflows/jarvis-cloud.yml). Använd min befintliga inloggning.
   Öppna Actions och arbetsflödets manuella startformulär.
   Stanna om rätt konto eller formulär inte är tillgängligt.

3. Visa en förhandsgranskning med exakt uppdragstext, avsedd modellprofil,
   tier, godkänd kodversion och platsen där resultatet ska sparas.
   Hugging Face-profilen är endast för textutkast från lämnat material.
   Den söker inte på webben och får inte hämta privat minne, skicka
   meddelanden, skriva till Notion eller utföra affärsåtgärder.

4. För HF: provider=huggingface, tier enligt den särskilt godkända
   HF-konfigurationen, notion_page_id tomt och verify_huggingface=false.
   Kopiera inte nycklar. Fyll inte på krediter eller ändra någon spärr.
   Om provider-fältet saknas är den förberedda versionen inte i bruk:
   byt inte till en gammal API-väg eller annan modell som reserv.

5. Använd endast en separat godkänd driftsatt kodversion. Kör inte den
   större utvecklingsgrenen bara för att den går att välja i formuläret.
   Saknas modellval, leverantör, pris-/budgetunderlag, datagodkännande
   eller aktivering: redovisa vad som saknas och stanna.

6. Klicka INTE på den knapp som skickar eller startar körningen.
   Svara "Förberett, inte startat" och lämna granskningsunderlaget.
   Om jag senare vill starta krävs ett separat uttryckligt startbeslut
   för exakt uppdrag, destination, kodversion och kostnadsram.
   Vid timeout eller oklar kvittens: gör inget automatiskt återförsök.

Försök aldrig använda den äldre jarvis-comet GET-vägen för vanliga uppdrag.
Lägg aldrig en nyckel i query-parametern k. Comet-webbläsaren och CometAPI
är skilda saker; den ena anslutningen bevisar inte att den andra fungerar.
```

## Tre förberedda uppdragsexempel

- **Sammanfattning:** `Sammanfatta följande icke-känsliga anteckningar i högst fem
  punkter. Använd bara texten och markera sådant som saknas: [material].`
- **Prioritering:** `Gör en nästa-steg-lista av dessa aktiviteter. Motivera ordningen
  utifrån de mål och tidsgränser som anges; gissa inga kostnader: [aktiviteter].`
- **Rutinutkast:** `Skriv ett kort utkast till intern rutin utifrån dessa steg.
  Skilj givna krav från förslag och ange öppna frågor: [steg].`

Inga exempel skickar meddelanden, köper tjänster eller uppdaterar affärssystem.
Kundhandlingar, avtal, personaldata, betalningar och hemligheter ingår inte i den
första HF-profilen; klassificering med nyckelord är inte ett fullständigt dataskydd.

## Senare installation och verifiering

1. Läs först eventuell befintlig `/jarvis` i Comets inställningar.
2. Granska eller spara ovanstående prompt via Comets genvägsfunktion. Behåll
   användarens val av modell och läge om inget annat beslutats.
3. Prova endast med ett ofarligt exempel fram till förhandsgranskningen.
4. Verifiera rätt repo, profil och att ingen körning registrerades.
5. Först därefter kan separat startgodkännande och ett begränsat pilotprov behandlas.

Detta dokument gör inte installationen. Ett grönt lokalt test av Jarvis-koden
är heller inte ett gränssnittstest av Comet.
