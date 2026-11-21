# JARVIS Kontrollrum (dashboard)

Mobilanpassad PWA för Rickys Jarvis: KPI, initiativ, systemläge, connector-hälsa, händelser, minne och chatt med JARVIS Prime.

- Frontend: Vite + React + Tailwind, statisk export (`npm run build` → `dist/`). Hostas på Vercel.
- Backend: Supabase Edge Function `supabase/functions/jarvis-dashboard-api` (service role server-side, nyckelgrind `x-jarvis-key`).
- Chatt: `prime` = repository_dispatch `jarvis-run` → `jarvis_cloud.py` skriver svaret till `public.jarvis_chat`; `instant` = OpenAI-kompatibel LLM om secret `LLM_API_KEY` finns.
- Inloggning: Jarvis-nyckeln (JARVIS_ENDPOINT_KEY) eller ett lösenord vars SHA-256 ligger i `system_config.dashboard_password_sha256`.

Bygg lokalt: `npm install && npm run build`. Miljövariabel `VITE_JARVIS_API_URL` kan peka om API:t (default: produktionsfunktionen).
