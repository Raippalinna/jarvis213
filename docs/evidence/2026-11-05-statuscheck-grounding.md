# 2026-11-05 — Daglig statuscheck: verifierad hallucinationsloop och åtgärd

## Observation (läst 2026-11-05, inte antaget)

- Notion Control Room (sida `3ca66d43-c107-813b-90f3-daf5b5a42333`) innehöll 76 JARVIS-toggles.
  Frasen "Resursbrist på utvecklare" förekom 15 gånger och "rekryteringskampanj" 14 gånger —
  Ricky har inget utvecklarteam; innehållet är påhittat.
- `jarvis_memory` i Supabase (`fzmnqvmfilqizzftphbt`): 37 wiki-rader (2026-08-29) och 34
  `conversation`-rader (2026-10-20 → 2026-11-04), samtliga `turn:cloud` från statuscheckar.
  Loopen började när samtalsturer började sparas (Memory v1, 2026-10-20): varje ny statuscheck
  hämtade gårdagens påhitt som "relevant historik" och byggde vidare på det.
- Körning 41831962073 (2026-11-04): `Frugality: LAST-RESORT`, kvalitet 1.0, `notion: ok 200`.
  Kvalitetsmåttet mäter struktur (tre numrerade punkter), inte sanningshalt.
- `notify_all` → Notion-sinken svarade `http 400 invalid_request_url`; `_post_to_notion_page`
  med workflow-indatan fungerade. Värdet i `NOTION_LOG_PAGE_ID` har alltså inte formen
  av ett rent sid-id (värdet har inte lästs, bara felkoden).

## Ändring i denna gren

1. PR #5 (minnesgrundning) sammanfogad: samtalsturer och genererade Notion-loggar utesluts ur
   kontexten, tomt minne sägs uttryckligen, grundningsregel i systemprompten, nyckelroll- och
   läsbarhetsdiagnostik.
2. Codex-granskningens punkter åtgärdade:
   - filtrering sker före resultatgränsen (överhämtning ×3, därefter tak),
   - `recent()` utesluter `conversation` redan i databasfrågan,
   - träffar dubbleras inte mellan semantiskt block och "senaste",
   - `sb_secret_*` räknas som serverbehörighet i nyckelrollsvarningen.
3. Notion-sinken normaliserar sid-id (UUID, URL eller råtext → 32 hex) i stället för att posta
   en ogiltig URL.
4. Tomt modellsvar avslutar inte kandidatkedjan: nästa kandidat provas, kostnaden summeras över
   alla nådda anrop, och bara om alla nåbara kandidater svarar tomt behålls platshållaren.

## Status

- TESTAT LOKALT: `python -m pytest tests -q` → 337 passerade (289 på main + 31 från PR #5 + 17 nya).
- Inte verifierat i drift förrän en `workflow_dispatch` av `jarvis-cron-daily.yml` körts efter merge
  och Notion-toggeln lästs tillbaka.

## Kvarstående beslut (inte ändrade här)

- `providers.yaml`: LOW-kedjans primärmodell (`gpt-4o-mini`, q=0.72) ligger under LOW:s eget
  kvalitetsgolv 0.75, därför `LAST-RESORT` varje dag. Ändring av tier-tabellen kräver uttryckligt
  uppdrag (AGENTS.md regel 5).
- De 34 påhittade `conversation`-raderna och de påhittade Notion-togglarna är inerta efter denna
  ändring men ligger kvar; radering är en destruktiv åtgärd som kräver godkännande.
- `NOTION_LOG_PAGE_ID`-värdet bör kontrolleras av Ricky i GitHub Secrets (normaliseringen
  räddar URL/UUID-format, inte ett helt felaktigt id).

## Driftverifiering 2026-11-05 (lästa körningar, inte antagna)

| Körning | Kod | Minne | Grundning | Kvalitet | Innehåll |
|---|---|---|---|---|---|
| 41831962073 (2026-11-04, före) | main 61c85d5 | pgvector-träffar = gårdagens svar | – | 1.0 | "Resursbrist på utvecklare", "rekryteringskampanj" (påhitt) |
| 41994361910 (efter #29, Control Room) | main f8a042d | pgvector=0 senaste=0 notion=ja wiki=2 | – | 1.0 | Loopen bruten, men modellen hittade på "materialförsening" och "projektledarmöte" |
| 41994995349 (gren, utan Notion-sida) | källkontroll v1 | samma | 0/3 (källa inline → regex) | 0.5 (tak) | Citerade Beslutslogg "BTF mappsystem 00–18"; punkt 3 "Inget registrerat" |
| 41995225214 (gren, utan Notion-sida) | källkontroll v2 | samma | 3/3, 1 "inget registrerat" | 1.0 | Inga påhittade händelser; källa per punkt |

Kostnad per körning ≈ 0,004 kr. `Frugality: LAST-RESORT` kvarstår tills #30 (LOW-golv 0,70) är
mergad; därefter ska körningarna visa `Tier=LOW chain[0]`.

Kvar efter detta: källkontrollen mäter källmärkning, inte sanning. En modell kan fortfarande
felcitera en post. Nästa billiga steg är att verifiera att den citerade posttiteln faktiskt
förekommer i kontexttexten (strängmatchning), vilket inte är gjort här.
