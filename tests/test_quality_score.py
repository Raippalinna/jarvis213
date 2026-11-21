"""Kvalitetsscore ska mäta det uppgiften bad om — inte tvinga RICKY-strukturen på korta svar.

Bakgrund (produktionsloggar i Notion Control Room 2026-09-02 … 2026-09-25):
- 503 model_not_found-svar fick 0.15 eftersom texten innehöll "kr".
- Korrekta statuscheckar med "(1)…(3), max 400 ord" fick 0.15 och utlöste
  KVALITETSAVVIKELSE-larm trots att svaret var exakt det som begärts.
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# Testerna ska vara nyckelfria och får inte nå nätet.
os.environ.setdefault("JARVIS_NOTIFY", "0")

from jarvis.core import supervisor as sv  # noqa: E402


STATUS_TASK = (
    "Daglig statuscheck: (1) Namnge dagens största flaskhals över alla initiativ, "
    "(2) en konkret handling att göra idag som ger mest hävstång, (3) något som "
    "ändrat sig sedan igår som kräver reaktion. Kort och skarpt — max 400 ord."
)
STATUS_ANSWER = (
    "1. Flaskhals: godkännanden från leverantörer i fasadprojektet Kungsgatan 37.\n"
    "2. Konkret handling: möte med Devex AB i dag, 30 min, låser tidsplanen (ca 20 tkr i risk).\n"
    "3. Förändring: inget nytt sedan igår som kräver reaktion."
)
STRATEGY_TASK = "Ge veckans ekosystem-briefing med rekommendationer och kr-effekt."
STRATEGY_ANSWER = (
    "Slutsats: fokusera kassaflödet.\nMöjligheter: 1,2 Mkr netto.\nRisker: förseningar.\n"
    "Dolda risker: resursallokering.\nHävstång: automatisering.\nRekommendation: prioritera.\n"
    "Nästa steg: möte inom 3 dagar."
)


class QualityScoreTests(unittest.TestCase):
    def test_error_answer_scores_zero(self):
        err = "[JARVIS-fel] Kunde inte anropa Comet (mellan): 503 model_not_found ... ~0.1442 kr"
        self.assertEqual(sv._quality_score(err, STRATEGY_TASK), 0.0)

    def test_empty_answer_scores_zero(self):
        self.assertEqual(sv._quality_score("", STATUS_TASK), 0.0)
        self.assertEqual(sv._quality_score("   ", ""), 0.0)

    def test_one_line_confirmation_passes_low_floor(self):
        task = "Kopplingstest: svara med en rad som bekräftar att Comet-vägen fungerar. Inga åtgärder."
        score = sv._quality_score("Kopplingstest bekräftat: Comet-vägen fungerar.", task)
        self.assertGreaterEqual(score, 0.75)

    def test_statuscheck_with_all_items_passes_low_floor(self):
        score = sv._quality_score(STATUS_ANSWER, STATUS_TASK)
        self.assertGreaterEqual(score, 0.75)

    def test_statuscheck_missing_items_is_penalised(self):
        partial = "1. Flaskhals: leverantörsgodkännanden."
        full = sv._quality_score(STATUS_ANSWER, STATUS_TASK)
        self.assertLess(sv._quality_score(partial, STATUS_TASK), full)

    def test_word_limit_breach_is_penalised(self):
        long_answer = STATUS_ANSWER + (" ord" * 700)
        self.assertLess(sv._quality_score(long_answer, STATUS_TASK), sv._quality_score(STATUS_ANSWER, STATUS_TASK))

    def test_full_strategic_answer_scores_one(self):
        self.assertEqual(sv._quality_score(STRATEGY_ANSWER, STRATEGY_TASK), 1.0)

    def test_strategic_answer_missing_sections_scores_lower(self):
        thin = "Slutsats: fokusera kassaflödet. Det blir bra."
        self.assertLess(sv._quality_score(thin, STRATEGY_TASK), 0.85)

    def test_legacy_call_without_task_still_works(self):
        # Bakåtkompatibelt: gammalt anrop utan task får inte krascha.
        self.assertIsInstance(sv._quality_score(STRATEGY_ANSWER), float)

    def test_base_prompt_does_not_force_seven_sections_always(self):
        self.assertNotIn("Svara ALLTID på svenska i exakt denna ordning", sv.BASE_SYSTEM)
        self.assertIn("Slutsats, Möjligheter, Risker, Dolda risker, Hävstång, Rekommendation, Nästa steg", sv.BASE_SYSTEM)
        self.assertIn("Hitta aldrig på siffror", sv.BASE_SYSTEM)


if __name__ == "__main__":
    unittest.main()
