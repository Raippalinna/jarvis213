"""Offline readiness report; never calls a model or exposes credential values."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis.routing.huggingface import require_budget, require_profile, selected
from jarvis.routing.providers import ProviderCatalog
from jarvis.routing.tiers import NoEligibleRoute


def report() -> dict:
    catalog = ProviderCatalog()
    status = catalog.integration_status["huggingface"]
    ready = False
    if status == "configured":
        try:
            profile = require_profile(catalog)
            require_budget(catalog)
            ready = os.environ.get("JARVIS_TIER", "LOW") == profile.tier
            status = "configured_for_review" if ready else "tier_mismatch"
        except NoEligibleRoute as exc:
            status = exc.status
    return {
        "status": status, "selected": selected(), "configuration_ready": ready,
        "task_checks_pending": True, "completion_requests": 0, "inference_tested": False,
        "billing_reconciled": False, "automatic_fallback": False,
    }


if __name__ == "__main__":
    result = report()
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["configuration_ready"] else 2)
