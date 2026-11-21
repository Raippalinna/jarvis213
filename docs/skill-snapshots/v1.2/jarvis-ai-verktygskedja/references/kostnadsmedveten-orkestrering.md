# Kostnadsmedveten orkestrering

Användaren föredrar matematiskt precisa, direkta svar och välgrundade invändningar. Optimera för löst uppgift och korrekthet, inte maximal modellstorlek eller antal verktyg.

## Arbetsordning

1. Definiera verifierbart resultat, felkonsekvens och dataklass. Läs relevant minne och befintlig artefakt före ny research; ge varje faktaunderlag källa och mättid.
2. Pröva kod, exakt återanvändning eller minsta källuppslag före generering. Skicka inte hela kontrollrummet när frågan gäller en källa. Cache måste bindas till identitet, källversion, profil och uppgift; gammalt är inte live.
3. Välj enklaste tillräckliga modell med aktuell tillgänglighet och godkänd datadelning. Använd starkare resonemang för komplex matematik, arkitektur, kausalitet, existentiell analys och hög felkonsekvens. Behov av nya fakta löses med källor, inte enbart större modell.
4. Kontrollera resultatet med facit, test, källstöd eller oberoende invändning. Modellens självförtroende och modellrådets enighet är inte bevis. Vid schemafel, saknad källa eller motsägelser: begränsa svaret eller föreslå en avgränsad nästa kontroll, inte obegränsade betalda återförsök.
5. Redovisa faktisk väg och verifieringsnivå. Mät modellförsök, cache, token där de returnerats, latens och fel; härled inte Computer-krediter ur API-priser eller token. Klart när resultat, test och återstående osäkerhet är synliga.

Exempel: `17,5 % av 1 200` → Decimal-beräkning `210`, inget modellanrop.
`Vilken arkitektur klarar kraven?` → relevanta krav/kod, starkare resonemang och tester; inte hela privata projektminnet.

## Abonnemang och verklig överlämning

- **Perplexity/Comet:** Ask och Comet Search förbrukar enligt [Perplexitys kreditvillkor](https://www.perplexity.ai/help-center/en/articles/13838041-how-credits-work-on-perplexity) inga Computer-krediter; Computer/Work gör det. Att Computer styr en webbläsare är inte samma sak som manuell gratis sökning. Ändra inte plan eller påfyllning.
- **ChatGPT Go:** API-användning ingår inte enligt [OpenAI](https://help.openai.com/en/articles/11989085-what-is-chatgpt-go). Återanvänd befintlig webbåtkomst där den passar, utan att extrahera cookies eller presentera den som app-API.
- **Microsoft 365/Copilot:** vissa API:er ingår för kvalificerande licenser enligt [Microsofts kostnadsvillkor](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/cost-considerations). Verifiera användarens exakta licens, konto och delegerade behörighet; anta varken fri åtkomst eller att API-vägen saknas.
- **Computer MCP:** [officiell OAuth-brygga](https://docs.perplexity.ai/docs/getting-started/integrations/computer-mcp-server) med riktigt `thread_id`. Märk FÖRBERETT, SKICKAT och ÅTERLÄST separat. Innan autentiserat rundtest: använd ett synligt manuellt kort med mål, minsta underlag, profilversion, destination och återkopplings-ID. Ett klistrat svar är ej verifierat tills det kontrollerats; kopierat kort är inte synkat minne.
- **Lokal Comet:** om vald dator är offline, bered uppdraget och säg vad som saknas. Använd inte en molnwebbläsare som om den vore användarens inloggade lokala session.

## Förslag som kräver användarbeslut

Förbättra befintlig väg före ny skill eller integration. Formulera förslag från observerade återkommande fel eller mätbar lucka: `observation → exakt ändring → nytta/osäkerhet → datadelning/kostnad → test → återställning`.

Nya leverantörer jämförs på uppgift, kvalitet, total kostnad, API-villkor och dataregion, inte ursprungsland. Använd offentliga eller syntetiska testfall innan privat material delas; ändra inte leverantör bara för en påstått låg prislista.

Verifiera föränderliga fakta i primärdokumentation, versionsanteckningar och faktisk connector/kod. Forum och YouTube får ge spår och designidéer, men verifiera metod, villkor och resultat innan de bär beslut.

Vid förslagsuppdrag: presentera skill-/promptändringar som en specifik diff för godkännande.
Vid uttryckligt genomförandeuppdrag: följ create-skill och spara den avgränsade ändringen i
befintligt scope efter validering; fråga inte igen om samma redan godkända åtgärd.
Godkänd beredning är inte installation, ny behörighet eller produktionssättning.
Registrera inte en bakgrundsbevakning utan ett separat definierat uppdrag, och kalla inte
förslagslådan självlärande eller AGI.
