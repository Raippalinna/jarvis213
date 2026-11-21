# JARVIS Ω∞ OS v2

## Comet-start och Hugging Face, förberedelse 2026-09-22

För vanliga textuppdrag finns nu en [förberedd Comet-start](clients/mobile/comet-start.md)
och en [avstängd Hugging Face-profil](docs/comet-hf-task-preparation.md).
Detta är utvecklingskod, inte installerad genväg eller driftsatt modellkörning.
HF väljs uttryckligen per manuell start, använder en bestämd modell och leverantör
och får inte automatiskt växla till en annan modell. Läs de nya instruktionerna
före äldre startbeskrivningar nedan; Comet-webbläsaren är inte CometAPI.

## Current safety candidate, 2026-09-20

This branch is tested development code, not a production deployment.
Read [API and safety completion notes](docs/completion-api-safety-20260920.md)
before using the older setup sections below. The release notes supersede legacy
claims about semantic memory, default credentials, monthly metering and fallbacks.

Missing switch access, missing budget input, or missing memory ownership now
fails closed. Perplexity Router is opt-in and remains disabled by default.
No production secrets, database schema, billing settings or schedules were changed.

**Cloud AI-hjärna för Ricky Raippalinna — LangGraph + Frugality Agent + kostnadsdimmer.**

- Repo: privat, `rickyraippalinna/jarvis-omega-v2`
- Runtime: GitHub Actions (samma workflow som förut, förbättrad)
- Modellrouting: Frugality Agent väljer billigaste ADEKVATA väg per tier

---

## Kostnadsdimmer

Sätt `JARVIS_TIER` (env) eller välj i "Run workflow"-dialogen:

| Tier | Primärval | Fallback-kedja | Kvalitetsfloor | Max kr/anrop |
|---|---|---|---|---|
| **FREE** | Endast policygodkända, konfigurerat kostnadsfria modeller | Ingen betald reservmodell | 0.60 | 0.10 |
| **LOW** | Första kandidaten som klarar 0.75 | Groq eller befintlig Comet GPT-4o inom samma kostnadstak | 0.75 | 1.00 |
| **MED** | Comet GPT-4o | Konfigurerad Sonnet-kandidat, tillgänglighet måste testas | 0.85 | 10.00 |
| **HIGH** | Konfigurerad Comet Opus-kandidat | Endast kandidater som klarar 0.90 | 0.90 | 50.00 |

Månadsbudget: `200 kr` (soft alert 50 %, hard alert 80 %, tvinga FREE vid 95 %).
Redigera i `src/jarvis/routing/providers.yaml`.

---

## Frugality Agent (Snålhetsagenten)

**Regler (deterministisk kod, inte LLM):**
1. Har taskens intent en API-tillgänglig gratis-kanal med kvalitet ≥ floor? → använd den.
2. Passar en redan-betald premium-kanal (M365 Copilot, ChatGPT Go) bättre + besparing ≥ 5 kr + tid ≤ 3 min? → skicka Slack/Notion-avisering.
3. Är taskens känslighet ≥ Confidential? → hoppa över providers som tränar på data.
4. Är månadsspend ≥ 95 %? → tvinga FREE oavsett vald tier.
5. Efter kör: om kvalitet < floor → auto-eskalera + AVISERA.

**Aviseringar går till** Slack + Notion Beslutslogg vid: BUDGET-alert, HANDOFF-förslag, KVALITETSAVVIKELSE. Tystnad om inga nycklar är satta.

---

## Setup (engångsjobb)

### 1. Secrets

Gå till https://github.com/rickyraippalinna/jarvis-omega-v2/settings/secrets/actions och lägg till (alla valfria utom `COMET_API_KEY`):

| Secret | Krävs | Källa |
|---|---|---|
| `COMET_API_KEY` | Ja | Ny (roterad) nyckel från cometapi.com |
| `GROQ_API_KEY` | Nej | https://console.groq.com/keys (gratis) |
| `CEREBRAS_API_KEY` | Nej | https://cloud.cerebras.ai (gratis) |
| `GOOGLE_AI_API_KEY` | Nej | https://aistudio.google.com/apikey (gratis) |
| `NOTION_TOKEN` | Nej | https://www.notion.so/my-integrations |
| `NOTION_LOG_PAGE_ID` | Nej | Sidan där alerts postas |
| `SLACK_WEBHOOK_URL` | Nej | Slack app → Incoming Webhooks |

### 2. Aktivera Actions (om ej klart)

https://github.com/rickyraippalinna/jarvis-omega-v2/actions

---

## Kör Jarvis

### A. GitHub UI (samma workflow som förut)

https://github.com/rickyraippalinna/jarvis-omega-v2/actions/workflows/jarvis-cloud.yml → **Run workflow** → skriv task, välj tier → **Run**.

### B. API-trigger (Notion-knapp, Slack, iPhone-genväg, Comet)

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GH_PAT" \
  https://api.github.com/repos/rickyraippalinna/jarvis-omega-v2/dispatches \
  -d '{
    "event_type": "jarvis-run",
    "client_payload": {
      "task": "Analysera ÄTA-läget Kungsgatan 37",
      "tier": "MED",
      "notion_page_id": "abc123..."
    }
  }'
```

### C. Lokalt

```bash
cp .env.example .env && $EDITOR .env
pip install -r requirements.txt
JARVIS_TIER=FREE TASK="Ge veckans ekosystem-briefing" python jarvis_cloud.py
```

---

## Resultat + observability

- `result.json` + `result.md` = artifact per körning (30 dagar).
- Notion Beslutslogg = alla Frugality-avvikelser (om `NOTION_LOG_PAGE_ID` satt).
- Slack-DM = samma alerts (om Slack-nyckel satt).
- Framtida: månadsrapport (fas 2).

---

## Minne (Fas 2)

Jarvis har tre minneslager som alla läses in i systempromten före LLM-anrop:

1. **Semantiskt (pgvector)** — tabellen `jarvis_memory` i din Supabase `fzmnqvmfilqizzftphbt`. Sparar samtalsturer, dokument-chunks, beslut. Hybridretrieval (70% cosine + 30% trigram). RLS aktiv, `anon` blockerad.
2. **Aktivt strukturerat (Notion Control Room)** — Beslutslogg + Ekosystem/Initiativ + Inkomst-radar. Kompakt brief injiceras.
3. **Arkitektoniskt (wiki)** — `wiki/`-snapshot av Perplexity project wiki, versionerad i repo:t.

Data-läckageskydd: chunks med sensitivity>=confidential filtreras bort när tier < MED, och embeddings-API anropas bara på Comet (tränar inte på data), aldrig Groq/Gemini.

Efter varje svar sparas Q+A automatiskt som ny chunk (fire-and-forget).

## Klienter (Fas 3)

Jarvis kan triggas från valfri enhet via `repository_dispatch`:

| Klient | Var | Filer |
|---|---|---|
| **VS Code / Node** | `Jarvis`-klass + CLI `npx jarvis "..."` | `clients/node/` |
| **Slack `/jarvis`** | Deno Deploy edge receiver | `clients/edge/slack-command.ts` |
| **iPhone Shortcut** | Siri: "Fråga Jarvis" | `clients/mobile/iphone-shortcut-setup.md` |
| **Comet-browser** | Förberedd genväg med startgranskning, ingen nyckel i webbadressen | [Comet-start](clients/mobile/comet-start.md) |

Alla kräver en fine-grained PAT med `contents:write` + `actions:write` på detta repo.

## Autonoma jobb (Fas 3)

Schemalagda workflows i `.github/workflows/`:

| Fil | När | Vad |
|---|---|---|
| `jarvis-cron-daily.yml` | 07:00 svensk tid | Daglig statuscheck (LOW-tier) |
| `jarvis-cron-weekly.yml` | Måndag 06:00 | Vecko-ekosystem-briefing (MED-tier) |
| `jarvis-cron-monthly-audit.yml` | 1:a 09:00 | Frugality-audit + narrativ syntes |

Alla postar till Notion Control Room + Slack automatiskt.

## Arkitektur

```
Trigger (workflow_dispatch / repository_dispatch)
        │
        ▼
jarvis_cloud.py → Supervisor.chat()
        │
        ▼
LangGraph:
  classify_intent → route → load_memory (pgvector+Notion+wiki)
    → frugality_preflight (välj billigaste ad. provider)
    → execute (vald provider/modell med minne i systemprompt)
    → reflect (kvalitetsscore + spara turen i pgvector)
    → frugality_audit (eskalera + AVISERA vid avvikelse)
        │
        ▼
result.json/md  +  Notion  +  Slack
```

Alla filer under `src/jarvis/routing/` och `src/jarvis/agents/frugality.py`.
