"""Fail-closed proposal gate. This module cannot install, merge or persist."""
from __future__ import annotations

import re
from datetime import datetime

from .evidence import assess_evidence, nonempty, valid_https_url
from .github import REPOSITORY

HASH = re.compile(r"[a-f0-9]{64}")
SHA = re.compile(r"[a-f0-9]{40}")
CRITICAL = {"success", "safety", "error", "empty", "fallback", "cancel", "sensitive"}


def review_proposal(proposal: object, *, now: datetime | None = None) -> dict:
    """Validate declared evidence, test reports and review, not their authenticity."""
    reasons: list[str] = []
    if not isinstance(proposal, dict):
        return {"status": "blocked", "reasons": ["proposal_required"]}
    for field in ("task", "relevance", "rollback", "author"):
        if not nonempty(proposal.get(field)):
            reasons.append(field + "_required")
    candidate_hash = proposal.get("candidate_hash")
    if not isinstance(candidate_hash, str) or HASH.fullmatch(candidate_hash) is None:
        reasons.append("candidate_sha256_required")
    if proposal.get("sensitivity") != "public":
        reasons.append("public_proposal_required")
    if proposal.get("cancelled") is not False:
        reasons.append("explicit_not_cancelled_required")
    if type(proposal.get("changes_code")) is not bool:
        reasons.append("changes_code_required")
    if proposal.get("changes_code") is True:
        version = proposal.get("source_version")
        license_review = proposal.get("license_review")
        source_url = proposal.get("source_url")
        prefix = "https://github.com/"
        pinned_path = source_url[len(prefix):] if (
            isinstance(source_url, str) and source_url.startswith(prefix)
        ) else ""
        pinned_parts = pinned_path.rsplit("/tree/", 1)
        if (not isinstance(version, str) or SHA.fullmatch(version) is None
                or not valid_https_url(source_url) or len(pinned_parts) != 2
                or REPOSITORY.fullmatch(pinned_parts[0]) is None
                or pinned_parts[1] != version):
            reasons.append("exact_source_pin_required")
        if (not isinstance(license_review, dict)
                or license_review.get("reviewed") is not True
                or license_review.get("source_version") != version
                or not nonempty(license_review.get("reviewer"))
                or not nonempty(license_review.get("license"))
                or license_review.get("license").strip().upper() in {"NOASSERTION", "UNKNOWN", "NONE"}
                or license_review.get("compatible") is not True):
            reasons.append("pinned_compatible_license_review_required")
    evidence = assess_evidence(proposal.get("evidence"), now=now)
    if evidence["status"] != "eligible_for_review":
        reasons.append("evidence_not_reviewable")
        reasons.extend("evidence:" + reason for reason in evidence["reasons"])
    review = proposal.get("independent_review")
    if (not isinstance(review, dict) or review.get("verdict") != "approved"
            or not nonempty(review.get("reviewer"))
            or (isinstance(proposal.get("author"), str)
                and " ".join(review["reviewer"].casefold().split())
                == " ".join(proposal["author"].casefold().split()))
            or review.get("candidate_hash") != candidate_hash):
        reasons.append("independent_candidate_review_required")
    evaluation = proposal.get("evaluation")
    if not isinstance(evaluation, dict):
        reasons.append("baseline_and_candidate_heldout_evaluation_required")
    else:
        reasons.extend(_review_evaluation(evaluation, candidate_hash))
    return {"status": "blocked" if reasons else "ready_for_review", "reasons": reasons}


def _review_evaluation(evaluation: dict, candidate_hash: object) -> list[str]:
    reasons: list[str] = []
    train_ids = evaluation.get("training_case_ids")
    baseline = evaluation.get("baseline")
    candidate = evaluation.get("candidate")
    if (evaluation.get("held_out") is not True or not isinstance(train_ids, list)
            or any(not nonempty(i, 200) for i in train_ids)
            or not isinstance(baseline, dict) or not isinstance(candidate, dict)):
        return ["baseline_and_candidate_heldout_evaluation_required"]
    if (not isinstance(baseline.get("hash"), str)
            or HASH.fullmatch(baseline["hash"]) is None
            or candidate.get("hash") != candidate_hash):
        reasons.append("evaluation_hash_binding_required")
    reports = []
    for name, report in (("baseline", baseline), ("candidate", candidate)):
        cases = report.get("cases")
        if not isinstance(cases, list) or not cases:
            return reasons + [name + "_cases_required"]
        mapped = {}
        for case in cases:
            if (not isinstance(case, dict) or not nonempty(case.get("id"), 200)
                    or not nonempty(case.get("category"), 100)
                    or not isinstance(case.get("outcome"), str)
                    or case["outcome"] not in {"PASS", "FAIL"}
                    or case["id"] in mapped):
                return reasons + ["malformed_or_duplicate_evaluation_case"]
            mapped[case["id"]] = case
        categories = {case["category"] for case in cases}
        if not CRITICAL.issubset(categories):
            reasons.append(name + "_critical_categories_required")
        # A recorded baseline failure can be the defect this candidate fixes.
        # Candidate critical failures and any PASS -> FAIL regression still block.
        if name == "candidate" and any(
            case["category"] in CRITICAL and case["outcome"] != "PASS" for case in cases
        ):
            reasons.append(name + "_critical_failure")
        if set(mapped) & set(train_ids):
            reasons.append("heldout_overlaps_training")
        reports.append(mapped)
    before, after = reports
    if set(before) != set(after) or any(
        before[key]["category"] != after[key]["category"] for key in set(before) & set(after)
    ):
        reasons.append("same_heldout_comparison_required")
    if any(before[key]["outcome"] == "PASS" and after[key]["outcome"] != "PASS"
           for key in set(before) & set(after)):
        reasons.append("regression")
    return reasons
