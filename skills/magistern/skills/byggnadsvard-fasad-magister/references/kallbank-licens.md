# Källbank och licensregister

Lagringsplats (beslut 2026-10-04): privat Dropbox `00 RICKY - Arbetsyta/JARVIS OCH TITANOS/magistern/kallbank/`.
BTF:s OneDrive/SharePoint är läskälla, aldrig lagringsmål. Mappen avgör vad som får göras:

| Mapp | Licensklass | Tillåtet |
|---|---|---|
| `01-cc-by` | CC BY / CC BY-SA | ladda ner, citera med källangivelse |
| `02-public-domain` | public domain / CC0 / US federal | ladda ner, citera fritt, ange ändå källa |
| `03-intern-referens` | gratis PDF utan öppen licens | ladda ner för eget bruk, citera korta stycken, sammanfatta |
| `04-endast-lankar` | upphovsrättsskyddat eller AI-förbud | aldrig ladda ner; hänvisa med länk, kod eller rubrik |

Uppdatera tabellen när en källa läggs till. Kolumnen "Kontrollerad" är datum då licensen senast
lästes på källans egen sida.

## Register

| Källa | Utgivare | Licensklass | URL | Kontrollerad |
|---|---|---|---|---|
| Arkivsök, öppna data, webbtext | Riksantikvarieämbetet | 01 (CC BY/CC0 enligt RAÄ:s CC-policy) | https://www.raa.se/kulturarv/tillgangligt-kulturarv/sa-tillampar-vi-creative-commons-och-open-access/ | 2026-10-04 (sökträff, läs policysidan före nedladdning) |
| Att vårda sten | RAÄ | 01 | https://www.raa.se/kulturarv/byggnader/byggnadsvard/att-varda-sten/ | 2026-10-04 |
| Natursten i byggnader (länsserie) | RAÄ via DiVA | 03 tills DiVA-posten bekräftar licens | https://www.diva-portal.org/smash/get/diva2:1234513/FULLTEXT01.pdf | 2026-10-04 |
| Mälsåker stuckatur (br2008_13) | RAÄ | 01/03, kontrollera | https://www.raa.se/publicerat/br2008_13.pdf | 2026-10-04 |
| Byggnadshyttan Mälsåker 1993–1996 | DiVA | 03 | http://www.diva-portal.org/smash/get/diva2:1292548/FULLTEXT01.pdf | 2026-10-04 |
| Putsarbeten (2007) | Statens fastighetsverk | 03 (fri PDF, ingen angiven licens) | https://cms.sfv.se/Media/3dlp13wx/sfv-putsarbeten-2007.pdf | 2026-10-04 |
| Stenhandboken Restaurering m.fl. delar | Sveriges Stenindustriförbund | 03 | https://www.sten.se/stenhandboken/ | 2026-10-04 |
| ICOMOS-ISCS glossary stone deterioration | ICOMOS | 03 (fri PDF) | https://www.icomos.org/public/publications/monuments_and_sites/15/pdf/Monuments_and_Sites_15_ISCS_Glossary_Stone.pdf/ | 2026-10-04 |
| Preservation Brief 23 Ornamental Plaster | US National Park Service | 02 | https://www.nps.gov/orgs/1739/upload/preservation-brief-23-ornamental-plaster.pdf | 2026-10-04 |
| Stone Conservation: Overview of Current Research | Getty Conservation Institute | 03 (fri PDF, licens ej verifierad) | https://www.getty.edu/conservation/publications_resources/pdf_publications/pdf/stoneconservation.pdf | 2026-10-04 |
| Mur och puts, rapporter | Hantverkslaboratoriet GU | 03 | https://www.gu.se/hantverkslaboratoriet/mur-och-puts | 2026-10-04 |
| Produktblad kalkbruk, FAQ | Målarkalk | 03 (leverantörsblad) | https://www.malarkalk.se/media/produktdata | 2026-10-04 |
| Stockholmskällan, innerstadsinventeringen | Stockholms stad | 04 för bilder/PDF tills licens läst; metadata fri att citera | https://stockholmskallan.stockholm.se/ | 2026-10-04 |
| Stadsmuseets klassificering | Stockholms stad | 04 (webbtjänst) | https://stadsmuseet.stockholm/kunskap-och-samlingar/kulturmiljo/klassificering/ | 2026-10-04 |
| Stadsarkivets bygglov | Stockholms stad | 04 (tjänst; enskilda ritningar kan vara fria) | https://sok.stadsarkivet.stockholm.se/ | 2026-10-04 |
| AMA Hus, MER, MPB, Teknikhandboken | Svensk Byggtjänst m.fl. | 04, AI-förbud i villkoren | hänvisa med kod | 2026-10-04 |
| SAOB (etymologi stuck m.m.) | Svenska Akademien | 04, citera kort | https://www.saob.se/ | 2026-10-04 |

## Nedladdningsrutin

1. Läs licensraden i registret; saknas rad: lägg till den först med klass 04.
2. Ladda bara ner klass 01–03. Spara med filnamn `ÅÅÅÅ-utgivare-titel.pdf` i rätt mapp.
3. Skriv en sammanfattning på högst en sida i `kallbank/sammanfattningar/` med sidhänvisningar;
   det är sammanfattningen som normalt läses in i sessionen, inte hela PDF:en.
4. Uppdatera `MANIFEST.json` (fil, klass, URL, hash, datum) i magisternmappen.
