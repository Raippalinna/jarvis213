"""Helt offline regression för manuell P0-releasegrind."""
import json
import unittest

from scripts.check_release_blockers import (
    _RejectRedirect,
    _open_no_redirect,
    EXPECTED_REPOSITORY,
    P0_ISSUES,
    Unverifiable,
    issue_state,
    read_issue,
    release_preflight,
)


class StubResponse:
    status = 200

    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.data).encode("utf-8")


def fake_github(overrides=None):
    records = {
        n: {"number": n, "state": "closed", "state_reason": "completed"}
        for n in P0_ISSUES
    }
    records.update(overrides or {})

    def opener(request, timeout=0):
        assert timeout <= 12
        assert request.full_url.startswith("https://api.github.com/repos/")
        assert request.get_header("Authorization") == "Bearer synthetic_test_only"
        return StubResponse(records[int(request.full_url.rsplit("/", 1)[-1])])

    return opener


class ReleasePreflightTests(unittest.TestCase):
    def test_all_p0_completed_only_passes_issue_review(self):
        code, message = release_preflight(EXPECTED_REPOSITORY, "synthetic_test_only", fake_github())
        self.assertEqual(code, 0)
        self.assertIn("Inte ett tillstånd", message)

    def test_one_open_issue_fails_closed(self):
        code, message = release_preflight(
            EXPECTED_REPOSITORY,
            "synthetic_test_only",
            fake_github({52: {"number": 52, "state": "open", "state_reason": None}}),
        )
        self.assertEqual(code, 1)
        self.assertIn("#52", message)

    def test_not_planned_closure_is_not_accepted(self):
        code, _ = release_preflight(
            EXPECTED_REPOSITORY,
            "synthetic_test_only",
            fake_github({70: {"number": 70, "state": "closed", "state_reason": "not_planned"}}),
        )
        self.assertEqual(code, 2)

    def test_mismatching_issue_identity_is_rejected(self):
        self.assertRaises(Unverifiable, issue_state, {"number": 999, "state": "closed", "state_reason": "completed"}, 13)

    def test_pull_request_instead_of_issue_rejected(self):
        self.assertRaises(
            Unverifiable, issue_state,
            {"number": 13, "state": "closed", "state_reason": "completed", "pull_request": {}}, 13,
        )

    def test_wrong_repository_never_calls_network(self):
        code, _ = release_preflight("someone/other", "synthetic_test_only", fake_github())
        self.assertEqual(code, 2)

    def test_missing_token_rejected(self):
        code, _ = release_preflight(EXPECTED_REPOSITORY, "", fake_github())
        self.assertEqual(code, 2)

    def test_provider_error_fails_without_exposing_error_body(self):
        def raises(_request, timeout=0):
            raise RuntimeError("secret_value_should_never_print")
        code, message = release_preflight(EXPECTED_REPOSITORY, "synthetic_test_only", raises)
        self.assertEqual(code, 2)
        self.assertNotIn("secret_value", message)

    def test_malformed_response_fails(self):
        def broken(_request, timeout=0):
            return StubResponse({"invalid": "document"})
        code, _ = release_preflight(EXPECTED_REPOSITORY, "synthetic_test_only", broken)
        self.assertEqual(code, 2)

    def test_redirects_never_forward_github_authorization(self):
        # Redirect handling must refuse all redirects, even to an HTTPS host.
        from urllib.request import Request
        original = Request(
            "https://api.github.com/repos/rickyraippalinna/jarvis-omega-v2/issues/52",
            headers={"Authorization": "Bearer synthetic_test_only"},
        )
        redirect = _RejectRedirect().redirect_request(
            original, None, 302, "Found", {},
            "https://other-host.example/collect",
        )
        self.assertIsNone(redirect)

    def test_default_http_transport_uses_no_redirects(self):
        self.assertIs(read_issue.__defaults__[0], _open_no_redirect)
        self.assertIs(release_preflight.__defaults__[0], _open_no_redirect)

    def test_non_200_response_fails(self):
        def failed(_request, timeout=0):
            return StubResponse({}, status=429)
        code, _ = release_preflight(EXPECTED_REPOSITORY, "synthetic_test_only", failed)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
