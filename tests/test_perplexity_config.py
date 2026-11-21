"""Deterministic config checks; no model-quality or live-service claims."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_perplexity_config import (
    ConfigError, DEFAULT_MANIFEST, TARGETS, compare_observed, main, normalize,
    utf16_length, validate, validate_text,
)


ROOT = Path(__file__).resolve().parents[1]


class PerplexityConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / DEFAULT_MANIFEST
        self.manifest.parent.mkdir(parents=True)
        self.data = {
            "schema_version": 1,
            "purpose": "Offline test.",
            "fields": [
                {"id": key, "scope": scope, "path": f"{key}.txt"}
                for key, (scope, _) in TARGETS.items()
            ],
        }
        for item in self.data["fields"]:
            (self.root / item["path"]).write_text("Test.\n", encoding="utf-8")

    def run_validate(self):
        self.manifest.write_text(json.dumps(self.data), encoding="utf-8")
        return validate(self.root, self.manifest)

    def test_repository_configuration(self):
        self.assertEqual(set(validate(ROOT, ROOT / DEFAULT_MANIFEST)), set(TARGETS))

    def test_valid_fixture(self):
        self.assertEqual(len(self.run_validate()), 4)

    def test_utf16_not_codepoints(self):
        self.assertEqual(utf16_length("\U0001f600"), 2)

    def test_exact_limit(self):
        self.assertEqual(len(validate_text("personal_instructions", "a" * 1499 + ".")), 1500)

    def test_over_limit(self):
        with self.assertRaises(ConfigError):
            validate_text("personal_instructions", "a" * 1500 + ".")

    def test_astral_characters_count_twice(self):
        with self.assertRaises(ConfigError):
            validate_text("personal_instructions", "\U0001f600" * 750 + ".")

    def test_empty(self):
        with self.assertRaises(ConfigError):
            validate_text("brain_instructions", " \n")

    def test_truncated_sentence(self):
        with self.assertRaises(ConfigError):
            validate_text("personal_instructions", "Tänk alltid:\n- Första ordningens ")

    def test_final_punctuation_does_not_prove_semantics(self):
        self.assertEqual(validate_text("personal_instructions", "X."), "X.")

    def test_control_character(self):
        with self.assertRaises(ConfigError):
            validate_text("brain_instructions", "Text\0.")

    def test_invalid_unicode(self):
        with self.assertRaises(ConfigError):
            validate_text("brain_instructions", "\ud800.")

    def test_line_endings(self):
        self.assertEqual(normalize("A.\r\nB.\r\n"), "A.\nB.")

    def test_spaces_not_silently_removed(self):
        self.assertEqual(normalize(" A. \n"), " A. ")

    def test_duplicate_id(self):
        self.data["fields"].append(self.data["fields"][0].copy())
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_duplicate_file(self):
        self.data["fields"][1]["path"] = self.data["fields"][0]["path"]
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_wrong_scope(self):
        self.data["fields"][0]["scope"] = "project"
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_unknown_target(self):
        self.data["fields"][0]["id"] = "security_settings"
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_incomplete_target_set(self):
        self.data["fields"].pop()
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_absolute_path(self):
        self.data["fields"][0]["path"] = str(self.root / "personal_instructions.txt")
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_path_escape(self):
        self.data["fields"][0]["path"] = "../outside.txt"
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as external:
            secret = Path(external) / "private.txt"
            secret.write_text("Do not read.", encoding="utf-8")
            link = self.root / "outside.txt"
            link.symlink_to(secret)
            self.data["fields"][0]["path"] = "outside.txt"
            with self.assertRaises(ConfigError):
                self.run_validate()

    def test_missing_file(self):
        (self.root / self.data["fields"][0]["path"]).unlink()
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_bool_not_version(self):
        self.data["schema_version"] = True
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_extra_status_not_allowed(self):
        self.data["deployed"] = True
        with self.assertRaises(ConfigError):
            self.run_validate()

    def test_readback_match(self):
        texts = self.run_validate()
        self.assertEqual(compare_observed(texts, texts.copy()), [])

    def test_readback_drift(self):
        texts = self.run_validate()
        observed = texts.copy()
        observed["brain_instructions"] = ""
        self.assertEqual(compare_observed(texts, observed), ["brain_instructions"])

    def test_readback_incomplete(self):
        with self.assertRaises(ConfigError):
            compare_observed(self.run_validate(), {})

    def test_readback_nontext(self):
        texts = self.run_validate()
        observed = texts.copy()
        observed["brain_instructions"] = None
        with self.assertRaises(ConfigError):
            compare_observed(texts, observed)

    def test_cli_no_remote_claim(self):
        self.run_validate()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--root", str(self.root)])
        self.assertEqual(result, 0)
        self.assertFalse(json.loads(output.getvalue())["remote_state_verified"])

    def test_cli_error_does_not_echo_private_input(self):
        self.manifest.write_text("PRIVATE_CANARY_VALUE invalid json", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--root", str(self.root)])
        self.assertEqual(result, 2)
        self.assertNotIn("PRIVATE_CANARY_VALUE", output.getvalue())

    def test_cli_drift_exit(self):
        self.run_validate()
        observed = self.root / "observed.json"
        observed.write_text(json.dumps({key: "Different." for key in TARGETS}), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--root", str(self.root), "--observed", str(observed)])
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
