#!/usr/bin/env python3
"""One user-approved model evaluation, not normal Jarvis routing."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import huggingface_preflight as hf

REPOSITORY = "rickyraippalinna/jarvis-omega-v2"
PILOT_ID = "HF-PILOT-20260922-QWEN4B-NSCALE"
WORKFLOW = f"{REPOSITORY}/.github/workflows/huggingface-pilot-20260922.yml@refs/heads/main"
MODEL = "Qwen/Qwen3-4B-Instruct-2507"
PROVIDER = "nscale"
URL = "https://router.huggingface.co/v1/chat/completions"
INPUT_ESTIMATE_BOUND = 2048
OUTPUT_LIMIT = 180
ESTIMATED_USD_CAP = Decimal("0.01")
MAX_RESPONSE_BYTES = 131072
PAYLOAD = {
    "model": f"{MODEL}:{PROVIDER}",
    "messages": [
        {
            "role": "system",
            "content": (
                "Du är Jarvis testassistent. Använd endast texten i "
                "användarmeddelandet. Svara på svenska med exakt ett JSON-objekt "
                "utan kodblock och utan extra fält: sammanfattning (sträng), "
                "nasta_steg (lista med två strängar). Inga påhittade uppgifter."
            ),
        },
        {
            "role": "user",
            "content": (
                "Fiktivt test: Projekt Alfa har fått materialet levererat. "
                "Underlaget ska kontrolleras innan arbetet startar. Efter "
                "kontrollen ska ett startdatum föreslås. Sammanfatta läget "
                "och ange nästa två steg i rätt ordning."
            ),
        },
    ],
    "max_tokens": OUTPUT_LIMIT,
    "temperature": 0,
    "n": 1,
    "stream": False,
    "response_format": {"type": "json_object"},
}


class PilotFailure(RuntimeError):
    """Only constant local reason codes may reach logs."""


def validate_context(env: dict, event: object, now: datetime) -> None:
    required = {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_WORKFLOW_REF": WORKFLOW,
        # The first dispatch consumes this dated workflow, even if it fails.
        "GITHUB_RUN_NUMBER": "1",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    if any(env.get(key) != value for key, value in required.items()):
        raise PilotFailure("wrong_context_or_pilot_already_consumed")
    if not isinstance(event, dict):
        raise PilotFailure("invalid_event")
    repo = event.get("repository")
    if not isinstance(repo, dict) or repo.get("full_name") != REPOSITORY:
        raise PilotFailure("wrong_repository")
    inputs = event.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != {
        "approval", "approved_sha", "guard_checked_at"
    }:
        raise PilotFailure("invalid_inputs")
    if inputs["approval"] != PILOT_ID:
        raise PilotFailure("approval_mismatch")
    sha = inputs["approved_sha"]
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PilotFailure("invalid_approved_commit")
    if sha != env.get("GITHUB_SHA"):
        raise PilotFailure("unapproved_code_version")
    try:
        checked = datetime.fromisoformat(inputs["guard_checked_at"].replace("Z", "+00:00"))
        if checked.tzinfo is None or now.tzinfo is None:
            raise ValueError()
        age = (now - checked).total_seconds()
    except (AttributeError, TypeError, ValueError):
        raise PilotFailure("invalid_controller_guard_time") from None
    if not 0 <= age <= 300:
        raise PilotFailure("controller_guard_expired")


def verify_catalog(catalog: object) -> tuple[Decimal, Decimal, Decimal]:
    try:
        rows = [row for row in catalog["data"] if row.get("id") == MODEL]
        if len(rows) != 1:
            raise ValueError()
        model = rows[0]
        if model["architecture"] != {
            "input_modalities": ["text"], "output_modalities": ["text"]
        }:
            raise ValueError()
        providers = [row for row in model["providers"] if row.get("provider") == PROVIDER]
        if len(providers) != 1:
            raise ValueError()
        provider = providers[0]
        if (
            provider.get("status") != "live"
            or provider.get("supports_structured_output") is not True
            or type(provider.get("context_length")) is not int
            or provider["context_length"] < INPUT_ESTIMATE_BOUND + OUTPUT_LIMIT
        ):
            raise ValueError()
        input_rate = Decimal(str(provider["pricing"]["input"]))
        output_rate = Decimal(str(provider["pricing"]["output"]))
        if not input_rate.is_finite() or not output_rate.is_finite():
            raise ValueError()
        if not (0 <= input_rate <= Decimal("0.01") and 0 <= output_rate <= Decimal("0.03")):
            raise PilotFailure("price_above_reviewed_rates")
    except (KeyError, TypeError, AttributeError, ValueError, InvalidOperation):
        raise PilotFailure("unusable_exact_model_provider_catalog") from None
    estimated = (
        input_rate * INPUT_ESTIMATE_BOUND + output_rate * OUTPUT_LIMIT
    ) / Decimal(1_000_000)
    # Byte-based allowance is a conservative estimate, not a billing guarantee.
    byte_estimate = 1024 + sum(
        len(message["content"].encode("utf-8")) for message in PAYLOAD["messages"]
    )
    if byte_estimate > INPUT_ESTIMATE_BOUND or estimated > ESTIMATED_USD_CAP:
        raise PilotFailure("estimated_budget_exceeded")
    return input_rate, output_rate, estimated


def post_completion(token: str) -> object:
    request = urllib.request.Request(
        URL,
        data=json.dumps(PAYLOAD, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "jarvis-single-synthetic-pilot",
        },
        method="POST",
    )
    # No automatic retry, fallback, streaming, tools, or redirect.
    opener = urllib.request.build_opener(hf.NoRedirect())
    with opener.open(request, timeout=25) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PilotFailure("response_too_large")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise PilotFailure("invalid_completion_json") from None


def validate_response(result: object, token: str) -> tuple[dict, dict]:
    try:
        if result["model"] not in {MODEL, PAYLOAD["model"]}:
            raise ValueError()
        choices = result["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError()
        choice = choices[0]
        if choice["finish_reason"] != "stop" or choice["message"]["role"] != "assistant":
            raise ValueError()
        text = choice["message"]["content"]
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError()
        # Never echo the credential even if a faulty upstream were to return it.
        if token in text or re.search(r"\bhf_[A-Za-z0-9]{12,}\b", text):
            raise PilotFailure("sensitive_response_not_logged")
        answer = json.loads(text)
        if not isinstance(answer, dict) or set(answer) != {"sammanfattning", "nasta_steg"}:
            raise ValueError()
        if not isinstance(answer["sammanfattning"], str) or not answer["sammanfattning"].strip():
            raise ValueError()
        steps = answer["nasta_steg"]
        if not isinstance(steps, list) or len(steps) != 2:
            raise ValueError()
        if any(not isinstance(step, str) or not step.strip() for step in steps):
            raise ValueError()
        usage = result["usage"]
        prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
        if type(prompt) is not int or type(completion) is not int:
            raise ValueError()
        if not (0 < prompt <= INPUT_ESTIMATE_BOUND and 0 < completion <= OUTPUT_LIMIT):
            raise PilotFailure("reported_usage_exceeds_estimate_or_limit")
        if usage.get("total_tokens") != prompt + completion:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise PilotFailure("invalid_or_incomplete_completion") from None
    return answer, {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def run_pilot(
    env: dict, event: object, report: dict, *,
    read_json=hf.request_json, complete=post_completion, now=None,
) -> None:
    validate_context(env, event, now or datetime.now(timezone.utc))
    token = env.get("HF_TOKEN", "")
    if not token or len(token) > 2048 or any(char.isspace() for char in token):
        raise PilotFailure("credential_missing_or_invalid")
    identity = read_json(hf.IDENTITY_URL, token)
    if not isinstance(identity, dict) or identity.get("name") != "rickyraippalinna":
        raise PilotFailure("account_mismatch")
    input_rate, output_rate, estimated = verify_catalog(read_json(hf.CATALOG_URL))
    report["estimated_max_usd"] = str(estimated)
    report["reviewed_commit"] = env["GITHUB_SHA"]
    report["completion_requests_attempted"] = 1
    # From this point a timeout or cancellation may still have incurred a charge.
    result = complete(token)
    answer, usage = validate_response(result, token)
    report.update({
        "status": "completion_received",
        "inference_response_received": True,
        "requested_route": PAYLOAD["model"],
        "answer": answer,
        "usage": usage,
        "usage_cost_at_catalog_rates_usd": str(
            (input_rate * usage["prompt_tokens"] + output_rate * usage["completion_tokens"])
            / Decimal(1_000_000)
        ),
        "quality_status": "manual_review_required_not_a_production_quality_score",
    })


def main() -> int:
    report = {
        "pilot_id": PILOT_ID,
        "completion_requests_attempted": 0,
        "inference_response_received": False,
        "normal_jarvis_routing_changed": False,
    }
    code = 1
    try:
        with Path(os.environ.get("GITHUB_EVENT_PATH", "")).open("rb") as stream:
            raw = stream.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise PilotFailure("event_too_large")
        run_pilot(dict(os.environ), json.loads(raw), report)
        code = 0
    except (PilotFailure, hf.PreflightFailure) as exc:
        report.update(status="stopped", reason=str(exc))
    except urllib.error.HTTPError as exc:
        report.update(status="http_error", http_status=exc.code)
        exc.close()
    except (urllib.error.URLError, TimeoutError, OSError):
        report.update(status="transport_error_no_retry")
    except KeyboardInterrupt:
        report.update(status="cancelled_no_retry")
        code = 130
    except Exception:
        report.update(status="unexpected_error_no_retry")
    print(json.dumps(report, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
