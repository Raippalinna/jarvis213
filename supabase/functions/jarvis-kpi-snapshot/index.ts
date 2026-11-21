// Retired endpoint. Scheduled KPI snapshots now execute inside PostgreSQL via pg_cron.
// Keep this function free of service-role credentials and external writes.
// Deploy with verify_jwt=true; anonymous requests must be rejected by the Supabase gateway.

Deno.serve((_req: Request): Response => {
  return new Response(
    JSON.stringify({
      ok: false,
      error: "retired",
      message: "KPI snapshots are executed by the private postgres-owned pg_cron job."
    }),
    {
      status: 410,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store"
      }
    }
  );
});
