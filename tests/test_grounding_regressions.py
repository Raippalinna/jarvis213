"""Regressioner för tomma källrader och flersiffriga listpunkter."""
import pytest
from jarvis.core import supervisor as sup


@pytest.mark.parametrize("source", [
    "Källa:", "Källa:   ", "**Källa:**", "Källa: ** **",
    "Källa:\nFortsatt påstående", "Källa: ` `",
])
def test_empty_source_is_unsourced(source):
    result = sup.grounding_check("1. Påstående.\n" + source)
    assert result["sourced"] == 0
    assert result["unsourced"] == 1


@pytest.mark.parametrize("count", [10, 11, 100])
def test_multi_digit_last_item_is_checked(count):
    answer = "".join(
        f"{i}. Punkt. Källa: wiki – x\n" for i in range(1, count)
    ) + f"{count}. Påstående utan källa."
    result = sup.grounding_check(answer)
    assert result["items"] == count
    assert result["sourced"] == count - 1
    assert result["unsourced"] == 1


@pytest.mark.parametrize("source", [
    "Källa: x", "**Källa:** x", "- källa : x", "KÄLLA: Notion",
    "Källa: `wiki – x`", "Källa: _wiki – x_",
])
def test_nonempty_source_formats_still_work(source):
    assert sup.grounding_check("1. Påstående. " + source)["sourced"] == 1


@pytest.mark.parametrize("answer", [
    "", "   ", "(tomt svar från modellen)", "[JARVIS-fel] syntetiskt fel",
])
def test_empty_and_error_answers_remain_unchecked(answer):
    assert sup.grounding_check(answer)["checked"] is False
