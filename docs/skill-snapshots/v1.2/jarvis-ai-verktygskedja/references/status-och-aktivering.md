# Status och aktivering per arm

Daterade observationer, inte eviga sanningar. Kontrollera på nytt innan du påstår att något fungerar.

## Observerat 2026-09-25/26 (via Rickys Comet-webbläsare och gh)

| Arm | Status | Bevis |
|---|---|---|
| Perplexity-projektet Jarvis | 42 connectors förvalda i projektinställningarna, inkl. Stripe, Google Photos, YouTube Data | Projekt → Inställningar → Anslutningar. Kvar i "Lägg till": Springer, OpticOdds, Spotify (avsiktligt utanför). |
| Inbyggda skills model-council, create-skill, control-local-browser | Tillgängliga i alla sessioner; kan inte kopieras in i projektet (`pplx skill list --scope global` gav 0 träffar) | Denna skill är kopplingen: den säger när de ska laddas. |
| Lenovo 21X6001TMX | Online med comet-bridge, filesystem, desktop_filesystem. PowerShell: "Windows sandbox is not provisioned". Lokal subagent: "inference not connected" (inga lokala modeller). | `list_devices`, `pplx_device__powershell.run`, `run_local_subagent`. |
| ChatGPT | Inloggad som Ricky Raippalinna, plan "Go" | chatgpt.com profilmeny. |
| Codex cloud | Aktivt, GitHub-miljöer: boost-sparkle-engine, chic-ai-boutique, direct-translate-godmode, green-system-pro, jarvis-core, jarvis-omega-v2, legal-insight-hub, perplexity-os, project-canvas, sentinel-alert | chatgpt.com/codex/cloud → "View all code environments". Inga uppgifter körda från Jarvis än. |
| Cursor | Inloggad i Comet 2026-09-26 (ricky.raippalinna@gmail.com, plan Free, Privacy Mode aktiv). GitHub kopplat (rickyraippalinna), Linear kopplat, Slack/Teams/Jira ej kopplade. cursor.com/agents: "Cloud Agents requires a Pro Account" – Cursor kan alltså inte köra uppdrag från Jarvis förrän Ricky själv väljer Pro (abonnemangsbeslut, inte Jarvis). | cursor.com/dashboard/settings, /integrations, /agents. |
| jarvis-omega-v2 | main, inga push-triggade workflows (endast schedule, workflow_dispatch, repository_dispatch). AGENTS.md mergad till main via PR #3 2026-09-25 (godkänt av Ricky). | `git clone`, `.github/workflows/*.yml`, `gh pr view 3`. |
| Lovable | Ingen Perplexity-connector. Inloggad i Comet 2026-09-26 (workspace "Ricky's appstore"). VERIFIERAT: projektet Enhanced Integration Engine (= boost-sparkle-engine/TITANOS, id 15644bfb-…) visar i historiken "Pushed from GitHub – AGENTS.md: Jarvis-regler för Lovable, Codex och Cursor" och merge-commiten; GitHub→Lovable-synken fungerar. Varning i editorn: "Workspace usage limit for AI reached – AI features are paused" – Lovable-agenten står still tills Ricky höjer gränsen (kostnadsbeslut). Övriga Lovable-synkade repon: legal-insight-hub, chic-ai-boutique, green-system-pro, project-canvas (Pintox, egen MCP-server), sentinel-alert – AGENTS.md mergad i alla (PR #1 vardera). Fler Lovable-projekt utan känd repo-koppling: Mälardalen Mur & Puts Platform, Noumi OS, Marketing Maestro AI, Shadow Mirror. | lovable.dev/projects/15644bfb-…, `gh api`. |

## Aktiveringssteg som bara Ricky kan göra

1. **Lenovo PowerShell och lokal subagent:** öppna Perplexity-appen på datorn → enhetsinställningar → aktivera Windows-sandbox/PowerShell och välj en lokal modell samt arbetsmappar (t.ex. `C:\Users\<ricky>\Jarvis`). Först då kan Jarvis inventera Cursor/Codex CLI och köra skript lokalt.
2. **Lovable:** höj AI-gränsen i workspace-inställningarna om Lovable-agenten ska kunna bygga igen (kostnadsbeslut). Jarvis kan efter godkännande klistra in Jarvis-regler i projektets Knowledge.
3. **Cursor:** Cloud Agents kräver Pro (abonnemangsbeslut). Därefter valfritt:
   - Jarvis styr Cloud Agents via webben i Comet (redan inloggad).
   - Cursor → Settings → Integrations → Slack: installera Cursor-appen i BTF/Jarvis-Slack. Då kan Jarvis starta agenter med `@Cursor` i en kanal via Slack-connectorn.
   - Cursor API-nyckel (Background Agents API) via Computers säkra credential-formulär, aldrig i chatten.
4. **Codex CLI i sandboxen (valfritt):** kräver OpenAI API-nyckel via säkert formulär (`custom-credentials`). Utan nyckel: använd Codex cloud-UI i lokal webbläsare eller GPT-subagent.
5. **Codex cloud-uppgift från Jarvis:** Ricky godkänner att Jarvis skickar uppgiften (formulär till extern tjänst). Standardmiljö: `rickyraippalinna/jarvis-omega-v2`, branch `main`, PR mot main.

## Vad som inte ska göras

- Byt inte plan, abonnemang eller modellleverantör som del av en koppling.
- Lägg inte in ChatGPT/Cursor/Lovable som datakällor; de är utförare mot GitHub. Supabase förblir produktionsdata, Notion kontrollrum.
- Skriv inte AGENTS.md-regler som strider mot projektinstruktionerna; AGENTS.md är en delmängd, inte en kopia.

## Rättelse 2026-09-26 09:45 – databas för TITANOS
Tidigare påstående att boost-sparkle-engine kör mot Jarvis-Supabase `fzmnqvmfilqizzftphbt` var fel. Verifierat: repots spårade `.env` pekar på Lovable Cloud `qkwmgvlqqagjozubnrlc`, `aiden-chat` svarar där (ping 200) och Jarvis-Supabase har bara `jarvis-comet` och `jarvis-kpi-snapshot`. Samma rättelse finns i öppen PR #2 i boost-sparkle-engine (från parallell session 2026-09-25 22:15, 37 filer: sann integrationsstatus, säkra notiser, `safeStorage`, integrationskontrakt). PR #2 är MERGEABLE/CLEAN och rör inte samma filer som PR #4. Merge = L2, Rickys beslut.
