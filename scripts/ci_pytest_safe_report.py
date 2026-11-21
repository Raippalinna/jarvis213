import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

source = Path("pytest-results.xml")
report = {"xml_present": source.exists(), "tests": 0, "failures": 0, "errors": 0, "skipped": 0, "details": []}
if source.exists():
    try:
        root = ET.parse(source).getroot()
        for case in root.iter("testcase"):
            report["tests"] += 1
            if case.find("skipped") is not None:
                report["skipped"] += 1
            for tag, counter in (("failure", "failures"), ("error", "errors")):
                for node in case.findall(tag):
                    report[counter] += 1
                    text = (node.get("message", "") + " " + (node.text or ""))
                    types = sorted(set(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*(?:Error|Exception)\b", text)))
                    modules = sorted(set(re.findall(r"No module named ['\"]([a-zA-Z0-9_.]+)['\"]", text)))
                    report["details"].append({"index": report["tests"], "kind": tag, "exception_types": types[:10], "missing_modules": modules[:10]})
        report["details"] = report["details"][:30]
    except (ET.ParseError, OSError):
        report["parse_error"] = True
Path("pytest-safe-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
