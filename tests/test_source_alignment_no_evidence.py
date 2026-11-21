"""Regression: deklarerad avsaknad av källa är aldrig källstöd."""
import runpy
from pathlib import Path

import pytest

review = runpy.run_path(str(
    Path(__file__).resolve().parents[1] / "src/jarvis/intelligence/provenance.py"
))["review_source_alignment"]


@pytest.mark.parametrize("answer,context,status", [
    ("1. Materialet är försenat. Källa: inget registrerat", "JARVIS Prime", "insufficient_context"),
    ("1. Inget registrerat i minnet. Källa: inget registrerat", "JARVIS Prime", "insufficient_context"),
    ("1. Förslag. Källa: JARVIS Prime\n2. Försening. Källa: inget registrerat", "JARVIS Prime", "insufficient_context"),
    ("1. Fynd. Källa: Påhittad leverans\n2. Saknas. Källa: inget registrerat", "JARVIS Prime", "citation_mismatch"),
    ("1. Fynd utan källa\n2. Saknas. Källa: inget registrerat", "JARVIS Prime", "citation_mismatch"),
    ("1. Förslag. Källa: Notion/Initiativ – JARVIS Prime", "JARVIS Prime", "reviewable"),
    ("1. Förslag. Källa: JARVIS Prime", "", "insufficient_context"),
    ("", "JARVIS Prime", "not_applicable"),
    (None, "JARVIS Prime", "not_applicable"),
])
def test_status_precedence(answer, context, status):
    result = review(answer, context)
    assert result["status"] == status
    assert result["truth_verified"] is False


def test_sensitive_text_is_not_returned_in_diagnostics():
    result = review("1. SENSITIVE_TEST_VALUE. Källa: inget registrerat", "JARVIS Prime")
    assert "SENSITIVE_TEST_VALUE" not in str(result)
    assert result["no_evidence"] == 1
    assert result["matched"] == 0
    assert result["status"] == "insufficient_context"


def test_matching_title_never_verifies_claim_truth():
    result = review("1. Ett obelagt faktapåstående. Källa: JARVIS Prime", "JARVIS Prime")
    assert result["status"] == "reviewable"
    assert result["truth_verified"] is False
