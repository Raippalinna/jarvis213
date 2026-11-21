"""Explicit read-only capabilities. Never derive permission from model text."""
PROJECT = "fzmnqvmfilqizzftphbt"
READ_TOOLS = {
    "files": ["search_files_v2"],
    "gcal": ["search_email", "search_calendar"],
    "outlook": ["search_email", "search_calendar"],
    "notion_mcp": ["notion-get-tool-access", "notion-ai-search", "notion-search", "notion-fetch"],
    "supabase": ["get_project", "list_tables", "list_edge_functions"],
    "slack_direct": ["slack_search_public_and_private", "slack_read_thread"],
    "microsoft_365": ["sharepoint_search", "sharepoint_get_file_metadata"],
    "monday": ["get_board_info", "get_board_items_page", "list_workspaces"],
    "hubspot": ["get_user_details", "get_organization_details", "search_crm_objects"],
    "canva": ["search-designs", "get-design"],
    "lucid": ["search", "fetch"],
    "whimsical": ["search", "fetch"],
    "jam": ["search", "getDetails"],
    "quartr": ["search_companies", "get_company", "list_events", "read_transcript"],
    "youtube_data_api__pipedream": ["youtube_data_api-search-videos", "youtube_data_api-channel-statistics"],
    "youtube_analytics_api__pipedream": ["youtube_analytics_api-get-video-metrics"],
    "google_photos__pipedream": ["google_photos-get-media-item", "google_photos-list-library-contents"],
    "google_cloud_vision_api__pipedream": ["google_cloud_vision_api-detect-text-in-image"],
    "hugging_face": ["hub_repo_search", "hub_repo_details"],
    "linear_native": ["list_issues", "get_issue"],
    "neon": ["list_projects", "describe_project"],
}
ALIASES = {"dropbox": "files", "dropbox_mcp": "files", "google_drive": "files", "onedrive": "files"}
LOCKED = {
    "asana_mcp_merge": "Pausad enligt ditt tidigare beslut",
    "spotify__pipedream": "Privat tjänst, inte aktiverad i Jarvis",
    "legalzoom": "Inte avsedd för svensk juridik",
    "stytch": "Säkerhetsadministration kräver separat granskning",
    "stripe": "Betalningar och ekonomiska åtgärder låsta",
    "finance": "Separat finansflöde, inte aktiverat här",
    "posthog": "Kodexekvering kräver separat granskning",
    "amplitude": "Läsadapter ännu inte verifierad",
    "github_mcp_direct": "Kodåtkomst finns i Computer; webbadapter återstår",
    "vercel": "Driftsättningsadapter återstår",
}

def authorize_tool(source, tool, args, selected):
    allowed = {ALIASES.get(s, s) for s in selected}
    if source not in allowed or tool not in READ_TOOLS.get(source, []):
        raise PermissionError("Åtgärden finns inte i den valda läsbehörigheten.")
    if source == "supabase":
        key = "id" if tool == "get_project" else "project_id"
        if args.get(key) != PROJECT:
            raise PermissionError("Endast Jarvis Supabase-projekt är tillåtet.")
    return True
