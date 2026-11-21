"""Tomma modellsvar ska ha kvalitet noll; riktiga svar behåller sin poäng."""
import pytest
from jarvis.core import supervisor


@pytest.mark.parametrize("task", ["Status?", "Ge en rekommendation", "Svara med max 20 ord"])
@pytest.mark.parametrize("answer", [
    "(tomt svar från modellen)",
    "  (tomt svar från modellen)\n",
    "",
    " \n\t",
    "[JARVIS-fel] test",
])
def test_empty_model_answer_quality_zero(task, answer):
    assert supervisor._quality_score(answer, task) == 0.0


@pytest.mark.parametrize("task,answer,expected", [
    ("Status?", "Ett riktigt svar", 0.8),
    ("Status?", "Kostnad 10 kr", 0.85),
    ("Ge en rekommendation", "Slutsats: Möjligheter och risker. Rekommendation: nästa steg inom 2 dagar.", 1.0),
    ("Besvara (1) och (2)", "1. Första svaret\n2. Andra svaret", 0.9),
    ("Svara med max 20 ord", "Kort riktigt svar", 0.85),
])
def test_normal_answer_quality_unchanged(task, answer, expected):
    assert supervisor._quality_score(answer, task) == expected
