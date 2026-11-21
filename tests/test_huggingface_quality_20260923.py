"""Offline checks. No real credentials, network, or model calls."""
import copy
import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import huggingface_pilot_20260922 as baseline
from scripts import huggingface_quality_20260923 as p

NOW = datetime(2026, 9, 23, 6, 10, tzinfo=timezone.utc)
SHA = "a" * 40
TOKEN = "synthetic_test_credential"


def fixtures():
    env = {
        "GITHUB_REPOSITORY": p.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_WORKFLOW_REF": p.WORKFLOW,
        "GITHUB_RUN_NUMBER": "1",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": SHA,
        "HF_TOKEN": TOKEN,
    }
    event = {
        "repository": {"full_name": p.REPOSITORY},
        "inputs": {
            "approval": p.PILOT_ID,
            "approved_sha": SHA,
            "guard_checked_at": NOW.isoformat(),
        },
    }
    catalog = {"data": [{
        "id": p.MODEL,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "providers": [{
            "provider": p.PROVIDER, "status": "live", "context_length": 32768,
            "supports_structured_output": True,
            "pricing": {"input": 0.20, "output": 0.60},
        }],
    }]}
    answer = {
        "sammanfattning": "Materialet har levererats till Projekt Alfa.",
        "nasta_steg": ["Kontrollera underlaget.", "Föreslå därefter ett startdatum."],
    }
    result = {
        "model": p.MODEL,
        "choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(answer),
        }}],
        "usage": {"prompt_tokens": 150, "completion_tokens": 70, "total_tokens": 220},
    }
    return env, event, catalog, result


class QualityComparisonTests(unittest.TestCase):
    def test_workflow_only_allows_manual_execution_with_one_business_secret(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/huggingface-quality-20260923.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*(push|pull_request|schedule|repository_dispatch|workflow_call):")
        self.assertEqual(workflow.count("secrets."), 1)
        self.assertIn("secrets.HF_TOKEN", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("${{ inputs.", workflow)
        self.assertIn("timeout-minutes: 2", workflow)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", workflow)

    def test_review_document_contains_the_exact_outbound_payload(self):
        root = Path(__file__).resolve().parents[1]
        document = (root / "docs/huggingface-quality-20260923.md").read_text()
        payload = document.split("```json\n", 1)[1].split("\n```", 1)[0]
        self.assertEqual(json.loads(payload), p.PAYLOAD)

    def test_comparison_changes_only_the_model_in_the_outbound_payload(self):
        old_payload, new_payload = copy.deepcopy(baseline.PAYLOAD), copy.deepcopy(p.PAYLOAD)
        old_model, new_model = old_payload.pop("model"), new_payload.pop("model")
        self.assertNotEqual(old_model, new_model)
        self.assertEqual(old_model.rsplit(":", 1)[1], new_model.rsplit(":", 1)[1])
        self.assertEqual(old_payload, new_payload)
        self.assertNotEqual(baseline.PILOT_ID, p.PILOT_ID)
        self.assertNotEqual(baseline.WORKFLOW, p.WORKFLOW)

    def test_valid_single_request(self):
        env, event, catalog, result = fixtures()
        fetch = Mock(side_effect=[{"name": "rickyraippalinna"}, catalog])
        completion = Mock(return_value=result)
        report = {}
        p.run_pilot(env, event, report, read_json=fetch, complete=completion, now=NOW)
        self.assertEqual(fetch.call_args_list[0].args, (p.hf.IDENTITY_URL, TOKEN))
        self.assertEqual(fetch.call_args_list[1].args, (p.hf.CATALOG_URL,))
        completion.assert_called_once_with(TOKEN)
        self.assertEqual(report["status"], "completion_received")
        self.assertEqual(report["estimated_max_usd"], "0.0005176")
        self.assertNotIn(TOKEN, json.dumps(report))

    def test_valid_json_does_not_automatically_pass_semantic_quality(self):
        # Actual failure pattern from the earlier test: materialet != underlaget.
        env, event, catalog, result = fixtures()
        wrong_answer = {
            "sammanfattning": (
                "Projekt Alfa har fått materialet levererat och det ska nu "
                "kontrolleras innan arbetet startar. Efter kontrollen ska "
                "ett startdatum föreslås."
            ),
            "nasta_steg": [
                "Kontrollera materialet enligt underlaget",
                "Föreslå ett startdatum efter kontroll",
            ],
        }
        result["choices"][0]["message"]["content"] = json.dumps(wrong_answer)
        report = {}
        p.run_pilot(
            env, event, report,
            read_json=Mock(side_effect=[{"name": "rickyraippalinna"}, catalog]),
            complete=Mock(return_value=result), now=NOW,
        )
        self.assertEqual(report["status"], "completion_received")
        self.assertEqual(report["answer"], wrong_answer)
        self.assertEqual(
            report["quality_status"],
            "manual_review_required_not_a_production_quality_score",
        )
        self.assertNotIn("quality_index", report)
        self.assertNotIn("quality_passed", report)

    def test_bad_context_never_calls_network(self):
        for key, value in [
            ("GITHUB_RUN_NUMBER", "2"), ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_REF", "refs/heads/unreviewed"), ("GITHUB_REPOSITORY", "other/repo"),
            ("GITHUB_EVENT_NAME", "push"), ("GITHUB_WORKFLOW_REF", "other"),
            ("GITHUB_SHA", "b" * 40),
        ]:
            with self.subTest(key=key):
                env, event, _, _ = fixtures()
                env[key] = value
                fetch, completion = Mock(), Mock()
                with self.assertRaises(p.PilotFailure):
                    p.run_pilot(env, event, {}, read_json=fetch, complete=completion, now=NOW)
                fetch.assert_not_called()
                completion.assert_not_called()

    def test_bad_inputs_or_guard_never_calls_network(self):
        changes = [
            {"approval": "not-approved"},
            {"approved_sha": "invalid"},
            {"guard_checked_at": "2026-09-23T06:04:59+00:00"},
            {"guard_checked_at": "2026-09-23T06:10:01+00:00"},
            {"guard_checked_at": "2026-09-23T06:10:00"},
            {"guard_checked_at": None},
            {"task": "private customer text"},
        ]
        for changeset in changes:
            with self.subTest(changes=changeset):
                env, event, _, _ = fixtures()
                event["inputs"].update(changeset)
                fetch, completion = Mock(), Mock()
                with self.assertRaises(p.PilotFailure):
                    p.run_pilot(env, event, {}, read_json=fetch, complete=completion, now=NOW)
                fetch.assert_not_called()
                completion.assert_not_called()

    def test_wrong_account_or_missing_key_never_calls_model(self):
        for token in ["", "bad key", TOKEN]:
            env, event, _, _ = fixtures()
            env["HF_TOKEN"] = token
            completion = Mock()
            with self.assertRaises(p.PilotFailure):
                p.run_pilot(env, event, {}, read_json=Mock(return_value={"name": "other"}),
                            complete=completion, now=NOW)
            completion.assert_not_called()

    def test_bad_catalog_fails_closed(self):
        _, _, good, _ = fixtures()
        bad_catalogs = [{}, {"data": []}, {"data": good["data"] * 2}]
        for change in [
            {"status": "stopped"}, {"provider": "auto"},
            {"pricing": {"input": 0.21, "output": 0.60}},
            {"pricing": {"input": 0.20, "output": 0.61}},
            {"pricing": {"input": "NaN", "output": 0.60}},
            {"pricing": {"input": -1, "output": 0.60}},
            {"pricing": {}}, {"context_length": 100},
            {"supports_structured_output": False},
        ]:
            bad = copy.deepcopy(good)
            bad["data"][0]["providers"][0].update(change)
            bad_catalogs.append(bad)
        for catalog in bad_catalogs:
            with self.subTest(catalog=catalog):
                with self.assertRaises(p.PilotFailure):
                    p.verify_catalog(catalog)

    def test_timeout_and_cancel_never_retry_or_fallback(self):
        for failure in [TimeoutError(), KeyboardInterrupt(), RuntimeError("upstream")]:
            env, event, catalog, _ = fixtures()
            fetch = Mock(side_effect=[{"name": "rickyraippalinna"}, catalog])
            completion = Mock(side_effect=failure)
            report = {}
            with self.assertRaises(type(failure)):
                p.run_pilot(env, event, report, read_json=fetch, complete=completion, now=NOW)
            self.assertEqual(report["completion_requests_attempted"], 1)
            completion.assert_called_once()

    def test_empty_truncated_sensitive_or_wrong_output_rejected(self):
        _, _, _, good = fixtures()
        variants = []
        for text in ["", "not json", "{}", TOKEN, "hf_" + "x" * 24]:
            result = copy.deepcopy(good)
            result["choices"][0]["message"]["content"] = text
            variants.append(result)
        for key, value in [("model", "other/model"), ("choices", []), ("usage", {})]:
            result = copy.deepcopy(good)
            result[key] = value
            variants.append(result)
        truncated = copy.deepcopy(good)
        truncated["choices"][0]["finish_reason"] = "length"
        variants.append(truncated)
        too_many_tokens = copy.deepcopy(good)
        too_many_tokens["usage"]["completion_tokens"] = 181
        variants.append(too_many_tokens)
        for result in variants:
            with self.subTest(result=result):
                with self.assertRaises(p.PilotFailure):
                    p.validate_response(result, TOKEN)

    def test_exact_wire_payload_and_no_redirect(self):
        _, _, _, response = fixtures()
        transport_response = Mock()
        transport_response.read.return_value = json.dumps(response).encode()
        transport_response.__enter__ = Mock(return_value=transport_response)
        transport_response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = transport_response
        with patch.object(p.urllib.request, "build_opener", return_value=opener) as build:
            p.post_completion(TOKEN)
        self.assertIsInstance(build.call_args.args[0], p.hf.NoRedirect)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, p.URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), p.PAYLOAD)
        self.assertIsNone(request.get_header("X-hf-bill-to"))
        opener.open.assert_called_once()

    def test_main_does_not_log_remote_errors_or_secrets(self):
        error = urllib.error.HTTPError(p.URL, 401, TOKEN, {}, io.BytesIO(TOKEN.encode()))
        with patch.object(p.Path, "open") as opened:
            opened.return_value.__enter__.return_value.read.return_value = b"{}"
            with patch.object(p, "run_pilot", side_effect=error), redirect_stdout(io.StringIO()) as output:
                code = p.main()
        self.assertEqual(code, 1)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["http_status"], 401)


if __name__ == "__main__":
    unittest.main()
