#!/usr/bin/env python3
"""Read-only, deterministic JARVIS mission smoke run.

Runs only fixed local source compilation and offline unit tests. Produces a
machine-readable status report. No model, network, deployment, auth or business
workflows are activated; this is NOT production Jarvis execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from jarvis.core.mission_engine import (  # noqa: E402
    ExecutionEvidence, MissionEngine, MissionStatus, MissionStep,
)


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def attest_file(path: Path, *, condition: bool) -> tuple[ExecutionEvidence, object]:
    """Collect file evidence and a verifier restricted to this local run.

    This verifies actual local bytes plus the caller's execution condition;
    it does not certify an external action or CI run independently.
    """
    expected = digest(path.read_bytes())
    evidence = ExecutionEvidence(artifact_ref="sha256:" + expected, summary="local artifact")

    def verifier(received: ExecutionEvidence) -> str | None:
        if not condition or received != evidence:
            return None
        if not path.is_file() or digest(path.read_bytes()) != expected:
            return None
        return "local-sha256:" + expected

    return evidence, verifier


def run_checks() -> dict:
    engine = MissionEngine([
        MissionStep("source", "Compile local mission module", required_capabilities=("read_source",)),
        MissionStep("tests", "Run fixed, offline mission regression tests",
                    depends_on=("source",), required_capabilities=("run_tests",)),
    ])
    checks = {"source_compiled": False, "unit_tests_passed": False}
    with tempfile.TemporaryDirectory(prefix="jarvis-mission-") as folder:
        tmp = Path(folder)
        src = ROOT / "src/jarvis/core/mission_engine.py"
        if src.is_file():
            engine.start("source", capabilities=("read_source",))
            try:
                py_compile.compile(str(src), cfile=str(tmp / "mission_engine.pyc"), doraise=True)
                checks["source_compiled"] = True
            except (OSError, py_compile.PyCompileError):
                engine.fail("source", reason="execution_failed")
            else:
                evidence, verifier = attest_file(tmp / "mission_engine.pyc", condition=True)
                engine.submit("source", evidence)
                engine.verify("source", verifier)

        if engine.gate("tests", capabilities=("run_tests",)) == "ready":
            engine.start("tests", capabilities=("run_tests",))
            # Fixed local command, never arbitrary user-supplied shell.
            # Do not forward API keys, webhooks, tokens or provider credentials.
            safe_names = ("PATH", "HOME", "USERPROFILE", "TMP", "TEMP", "TMPDIR", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL")
            safe_env = {k: os.environ[k] for k in safe_names if k in os.environ}
            safe_env.update({"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "JARVIS_NOTIFY": "0", "DRY_RUN": "1"})
            try:
                process = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests/test_mission_engine.py", "-q"],
                    cwd=ROOT, env=safe_env, timeout=120, capture_output=True, text=True,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                engine.fail("tests", reason="execution_failed")
            else:
                checks["unit_tests_passed"] = process.returncode == 0
                # The report never contains process stdout, stderr or secrets.
                (tmp / "tests.json").write_text(
                    json.dumps({"passed": process.returncode == 0}), encoding="utf-8"
                )
                if process.returncode == 0:
                    evidence, verifier = attest_file(tmp / "tests.json", condition=True)
                    engine.submit("tests", evidence)
                    engine.verify("tests", verifier)
                else:
                    engine.fail("tests", reason="execution_failed")

    success = engine.status == MissionStatus.VERIFIED
    return {
        "schema_version": 1,
        "mission": engine.snapshot(),
        "checks": checks,
        "passed": success,
        "scope": "local_offline_read_only",
        "production_verified": False,
        "live_integrations_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline JARVIS Mission Engine smoke run")
    parser.add_argument("--output", default="mission-result.json", help="Local JSON report path")
    options = parser.parse_args()
    report = run_checks()
    destination = Path(options.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JARVIS offline mission checks: " + ("PASS" if report["passed"] else "FAIL"))
    print(f"Report: {destination}")
    print("Production/integration verification: NOT PERFORMED")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
