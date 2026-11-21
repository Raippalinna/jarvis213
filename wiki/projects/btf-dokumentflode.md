---
id: projects/btf-dokumentflode
item_type: wiki_page
semantic_type: project
title: BTF dokumentflöde, mappstruktur och mallar
description: Hur BTF:s anbud och projekt faktiskt flödar genom OneDrive-mapparna 1 ANBUDSBILAGOR, 2 ANBUD och 3 PROJEKT, med numrering, filnamn, K-kalkylmall, betalplan, ÄTA och kända fallgropar. Verifierat mot hela mappträdet 2026-09-26.
created_at: '2026-09-26T07:30:00+00:00'
updated_at: '2026-09-26T07:30:00+00:00'
---
# BTF dokumentflöde, mappstruktur och mallar

BTF:s verkliga arbetsfiler ligger i företags-OneDriven "BTF Plåt" under `Skrivbordet/Ricky/` med tre toppmappar: `1 ANBUDSBILAGOR`, `2 ANBUD/<år>/ÅÅNNN - Objekt` och `3 PROJEKT/PNNNN - Objekt`. Hela trädet (1 235 mappar, 4 626 filer) och fem mallfiler lästes 2026-09-26 via Comet; den anslutna Microsoft-connectorn pekar på privat OneDrive och ser inte dessa filer [cite:1].

## Numrering och filnamn

- **Anbud** `ÅÅNNN` (25001–25033, 26001–26009); status skrivs i mappnamnet (`KLAR`, `LOU`, `RAM avtal`). **Projekt** `PNNNN` (P1573–P1745). Vid vinst kopieras anbudsmappen in i projektet, t.ex. `P1705 - Brovägen/25024 - Danderyd Brovägen/` [cite:1].
- Filnamn: `<Doktyp> - <Objekt> - <ÅÅÅÅ-MM-DD> <Initialer>[ rev./vN].<ext>`; RR = Ricky Raippalinna, SH = Sebastian Hult. Kalkyl `K<anbudsnr> - <Objekt> <datum> RR.xlsx`, anbud `Anbud - <Objekt> - <datum> RR.docx` + pdf, mängder `Mängder <objekt> <datum> RR.pdf` (Bluebeam), betalplan `Betalplan P<nr> <Objekt> <datum> RR.xlsx`, byggdagbok `ÅÅÅÅ.MM.DD Veckodag <moment> ÄTA <n>.docx` [cite:1].
- Rekommenderad anbudsmappstruktur (senaste medvetna): `1. Anbud / 2. UE / 3. Material / 4. Kalkyl / 5. Handlingar`. 14 av 43 anbud är platta, ca 15 har bara FFU-mapp [cite:1].

## Projektmall NYTT MAPPSYSTEM BTF (00–18)

00 ANBUDSMAPP · 01 PROJEKTSTARTPÄRMAR · 02 AVTAL · 03 EKONOMI · 04 INKÖP · 05 KALKYLER · 06 TIDPLAN · 07 PROJEKTERING · 09 PROTOKOLL · 10 KVALITE · 11 MILJÖ · 12 ARBETSMILÖ · 13 ÄTA, FS, AO · 14 KORRESPONDENS · 15 MYNDIGHETER - MM · 16 BESIKTNING · 17 PROJEKTAVSLUT · 18 EFTERMARKNAD, med underkoder som `03.01 BETALPLAN`, `04.02.02 MALLAR INKÖP` (UE AB-U/ABT-U 07), `10.04 EGENKONTROLLER`, `14.04 BYGGDAGBOK`, `17.02 DU (DRIFT-O UNDERHÅLLSDOKUMENT)`. Stavningar ska matchas exakt. Mallen är Interoc-arv (mallfiler daterade 2025-01-22) [cite:1].

## Flöde anbud → projekt

FFU in → anbudsmapp → Bluebeam-mängder → K-kalkyl (kopia av senaste K-fil) → UE-förfrågningar (pdf + .msg sparas som bevis) → anbudsbrev på BTF-brevpapper + bilagor från `1 ANBUDSBILAGOR` (F-skatt, försäkring, Creditsafe, kollektivavtal, CV, referenser, verksamhetsmanual, Bas U/P, SKV 4820) → revision via nytt datum → status i mappnamn → kontrakt (02.01) → betalplan (03.01, versioneras tätt) → KMA-plan, kontrollplan, arbetsberedning (10) → AMP och skyddsronder (12) → APD-plan (15.09) → byggdagbok/ÄTA (14.04) → ÄTA-sammanställning xlsx i projektroten → slutbesiktning (16.02) → DU-pärm 01–15 (17.02) → slutmöte och kundutvärdering (17.03) [cite:1].

## Mallarnas innehåll

- **K-kalkylmall** (Peab/Interoc-arv "Kalkylmall20170401"): ett blad per byggdel med huvud objekt/beställare/datum, kalkyltimpris 430–440 + 22 resor = 452–462 kr/h, ackordsriktpunkt 230, Ba/Na-mängder (alla nyckeltal i kr/Na). Fem tabeller i ordning Material, Arbete (T-åtg × timpris), UE, Arbetsplatsomkostnader = TB1; TB2 = tjänstemän + Säkerhet 0,5 % + Garanti 1 % + Avdelningsomkostnader 3–6 %; TB3 = KGK 0–2 %; +12 % vinst; ANBUD avrundas till jämna tusen; TG1/TG2/TG3 och veckor eget arbete. Prisbibliotek som namngivna områden (Material, Arbete, UE, Arbetsplatsomkostnader, Avdelningsomkostnader) med kontoplan 41xx/43–49xx/48xx/9010/9110. Bibliotekens nivåer är 2015–2017 utan indexdatum [cite:1].
- **Betalplan**: blad `1.Grund` (projektstamdata med namngivna celler `aktivitet_*`, `BASP_*`, `BASU_*`) och `lyftplan ` (lyft var 31:e dag, andel per byggdel, innehållna medel 10 % upp till 5 % av kontraktssumman) [cite:1].
- **ÄTA**: `ÄTA-Sammanst.`, `ÄTA-Underrättelse (AB)` (AB 04-brev), `ÄTA(1)…ÄTA(60)` med arbete × 630 kr/h; godkänd ÄTA = "1" i K5; bladnamn får inte ändras [cite:1].
- **Anbudsmall**: Interoc-baserad med hjälptext i stilen `Rådstext Interoc` som ska raderas; löpande räkning 550–950 kr/h, arvode 15 %, giltighet 30 dagar (60 i nyare anbud) [cite:1].
- Detaljerad specifikation och rensad mall finns i Rickys skill `btf-mur-puts-kalkyl` (`references/kmall-struktur.md`, `references/mappar-och-dokumentflode.md`, `assets/K-mall_BTF_ren.xlsx`) [cite:1].

## Kända fallgropar

- Projektmallen kopierades från Spårvagnen med innehåll: `K25001 Spårvagnen…xlsx` och Spårvagnens betalplaner ligger i P1623, P1644, Smaragden 2 och P1705. Objektnamn i filnamn måste matcha projektmappen innan siffror används [cite:1].
- K-nummer driver från mappnamn (K25026 i mapp 25027, K25034 i 26001, K26002 i 26004): ta anbudsnummer från mappen. Kalkylblad kopieras med gammalt huvud (Ampeln 12 i K26009 Blåelden) [cite:1].
- Dubbla projektmappar (`FALKEN 6`/`P1654 - Falken 6`, `Moränvägen 5`/`P1745 - Moränvägen 5`, `P1644 …`/`… Kay`). Mappen `13 ÄTA, FS, AO` är tom; ÄTA lever under 14.04 och i xlsx i roten [cite:1].
- Tre timprisnivåer beroende på dokument: kalkyl 452–462, ÄTA 630, löpande räkning 550–950 kr/h [cite:1].
- Molnplatshållare (Files On-Demand) ger `ERR_FILE_NOT_FOUND` via Comet; sådana filer är ej lästa [cite:1].

## Karta mot designad Jarvis-struktur

00_INKORG ↔ `OneDrive_1_<datum>/` och zip i anbudsroten · 01_LEDNING ↔ `1 ANBUDSBILAGOR` · 03_ANBUD ↔ `2 ANBUD` · 04_PROJEKT ↔ `3 PROJEKT` med 00–18 · 05_REGISTER saknas (endast `Orderstock BTF 2024-2025.xlsx`) · 06_MALLAR-BTF utspritt i 04.02.02, 04.03.01, 04.04.01, 10.x, 16.02 · 99_ARKIV ↔ mappar märkta KLAR [cite:1].

## See also

- [[entities/bra-tak-och-fasad-hult]] — verksamhetsägare
- [[projects/fasadprojekt-kungsgatan-37]] — kalkyl i praktiken
- [[projects/aktiva-initiativ]] — beslutslogg

## References

[cite:1]: pplx://sessions/6cee5c15-69a8-4024-83b4-0bb5c0541d5b
