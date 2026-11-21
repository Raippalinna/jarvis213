# Hugging Face: modellregister och styrning (hf-model-governor)

Status 2026-10-04: Hugging Face är återinförd i Jarvis på Rickys beslut (ersätter bortvalet
2026-09-20). Repo-secret `HF_TOKEN` finns i `rickyraippalinna/jarvis-omega-v2` (satt 2026-09-22).
Qwen3-235B-provet 2026-09-23 klarade fem kvalitetskriterier med ett anrop. Vanliga HF-uppdrag är
inte aktiverade; allt här startar i status **labb**.

## Dataklasser

| Klass | Exempel | Får skickas till extern modell |
|---|---|---|
| Offentlig | RAÄ-rapporter, arkivritningar som är fria, egna foton av offentlig fasad utan personer | Ja |
| Syntetisk | konstruerade testfall | Ja |
| Intern | BTF-kalkyler, kundritningar, anbud, mejl | Nej, endast lokalt körd modell |
| Personlig | personuppgifter, Naturstensregistrets ägaruppgifter | Nej |

## Regler

1. Läs modellkortet: licens, version, avsedd användning. Logga i tabellen före första anrop.
2. Lås leverantör (`provider`) i skarpa körningar; `auto` kan byta leverantör tyst.
3. Token: fine-grained eller read, aldrig i kod, Dropbox eller chatt. Namnges, visas aldrig.
4. Ett anrop per test, ingen omkörning utan ny orsak; logga kostnad från HF:s användningsöversikt.
5. Modellens utdata är hypotes: transkription kontrolleras mot bild, skadedetektion mot platsbesök.
6. Status flyttas labb → pilot → aktiv bara efter dokumenterat test i `tester/hf/` och Rickys ok.

## Register

| Roll | Modell | Licens (kontrollera kortet) | Status | Första test |
|---|---|---|---|---|
| Handskrift, svensk 1600–1900-tal | Riksarkivet/trocr-base-handwritten-hist-swe-2 https://huggingface.co/Riksarkivet/trocr-base-handwritten-hist-swe-2 | se modellkort | labb | A: offentlig 1800-talsritning med text |
| HTR-pipeline | Riksarkivet HTRflow https://huggingface.co/blog/Gabriel/htrflow | se repo | labb | samma som ovan |
| Semantisk sökning i källbank | KBLab/sentence-bert-swedish-cased https://huggingface.co/KBLab/sentence-bert-swedish-cased | se modellkort | labb | sök i sammanfattningar |
| Flerspråkig sökning | BAAI/bge-m3 | se modellkort | labb | jämför med KBLab |
| Tal till text, platsbesök | KBLab KB-Whisper (välj storlek i https://huggingface.co/KBLab) | se modellkort | labb | egen diktering, offentligt innehåll |
| Generell bildbeskrivning | Florence-2 | se modellkort | labb, låg prioritet | jämför mot granskade exempel |
| Sprickdetektering | YOLO-baserade öppna modeller | licens ej kontrollerad | vilande | ingen tills licens läst |
| Textmodell (verifierad) | Qwen3-235B via nscale | enligt pilot 2026-09-23 | pilot | klar |

Rekommenderat första test: A (handskrift på offentlig ritning). Allt material är offentligt och
resultatet kan kontrolleras mot originalet.
