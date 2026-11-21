import unittest
from policy import authorize_tool, PROJECT

class PolicyTests(unittest.TestCase):
    def test_selected_read(self):
        self.assertTrue(authorize_tool("gcal", "search_email", {"queries": ["Jarvis"]}, ["gcal"]))
    def test_no_send(self):
        for name in ["send_email", "draft_email", "delete_draft", "update_calendar"]:
            with self.assertRaises(PermissionError):
                authorize_tool("gcal", name, {}, ["gcal"])
    def test_unselected(self):
        with self.assertRaises(PermissionError):
            authorize_tool("gcal", "search_email", {}, ["supabase"])
    def test_fixed_project(self):
        self.assertTrue(authorize_tool("supabase", "get_project", {"id": PROJECT}, ["supabase"]))
        with self.assertRaises(PermissionError):
            authorize_tool("supabase", "get_project", {"id": "different"}, ["supabase"])
    def test_no_sql(self):
        with self.assertRaises(PermissionError):
            authorize_tool("supabase", "execute_sql", {"query": "delete from event"}, ["supabase"])
    def test_frozen(self):
        for source in ["asana_mcp_merge", "spotify__pipedream", "stripe"]:
            with self.assertRaises(PermissionError):
                authorize_tool(source, "list", {}, [source])
    def test_storage_alias(self):
        self.assertTrue(authorize_tool("files", "search_files_v2", {}, ["dropbox"]))

if __name__ == "__main__":
    unittest.main()
