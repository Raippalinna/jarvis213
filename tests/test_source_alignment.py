"""Tests for deterministic reference alignment; no provider keys or network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis.intelligence.provenance import review_source_alignment

CONTEXT = "### Aktivt kontrollrum\n- JARVIS Prime\n### Wiki\n- jarvis-prime-systembygge"


def test_references_to_available_titles_are_reviewable_not_verified():
    answer = ("1. Utred kontrollpunkten. Källa: Notion/Initiativ – JARVIS Prime.\n"
              "2. Läs projektbeskrivningen. Källa: wiki – jarvis-prime-systembygge.")
    result = review_source_alignment(answer, CONTEXT)
    assert result["status"] == "reviewable"
    assert result["matched"] == 2
    assert result["truth_verified"] is False


def test_fabricated_source_is_rejected():
    result = review_source_alignment("1. Materialförsening. Källa: Notion – Materialmöte 2026-11-05", CONTEXT)
    assert result["status"] == "citation_mismatch"
    assert result["checks"] == ["reference_not_in_context"]


def test_missing_source_is_rejected():
    result = review_source_alignment("1. Ett faktapåstående utan källa.", CONTEXT)
    assert result["missing"] == 1 and result["status"] == "citation_mismatch"


def test_no_data_claim_is_never_mislabelled_as_supported():
    result = review_source_alignment("1. Inget registrerat i minnet. Källa: inget registrerat.", CONTEXT)
    assert result["no_evidence"] == 1 and result["matched"] == 0
    assert result["truth_verified"] is False


def test_only_a_provider_name_cannot_support_a_claim():
    result = review_source_alignment("1. Klart. Källa: Notion", CONTEXT)
    assert result["status"] == "citation_mismatch"


def test_context_absence_does_not_verify_anything():
    result = review_source_alignment("1. Klart. Källa: JARVIS Prime", "")
    assert result["status"] == "insufficient_context"


def test_multiple_citations_one_missing_source_blocks():
    result = review_source_alignment("1. Fynd. Källa: JARVIS Prime\nKälla: Hittepå-projekt", CONTEXT)
    assert result["matched"] == 1 and result["unmatched"] == 1
    assert result["status"] == "citation_mismatch"


def test_boundaries_prevent_partial_title_match():
    result = review_source_alignment("1. Fynd. Källa: Notion – JARVIS Prim", CONTEXT)
    assert result["status"] == "citation_mismatch"


def test_embedded_source_inline_and_numbered_ten():
    answer = "".join(f"{i}. Fynd. Källa: JARVIS Prime\n" for i in range(1, 11))
    result = review_source_alignment(answer, CONTEXT)
    assert result["items"] == 10 and result["matched"] == 10


def test_bad_types_fail_safely():
    assert review_source_alignment(None, CONTEXT)["status"] == "not_applicable"
    assert review_source_alignment("foo", None)["status"] == "insufficient_context"


def test_overlong_input_is_blocked():
    assert review_source_alignment("a" * 32001, CONTEXT)["status"] == "citation_mismatch"
