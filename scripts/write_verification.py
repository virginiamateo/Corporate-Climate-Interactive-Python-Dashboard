"""Run the verification commands and write reports/verification_report.md from their results.

Usage: python scripts/write_verification.py [--browser]

Every row of the results table is produced from a command that this script executes. Test
counts are read from the JUnit XML files written by pytest. Notes from a manual review are read
from reports/manual_review.md if that file exists.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PY = sys.executable

AREA_FILES = {
    "Source files": ["test_sources"],
    "Cleaning and integrity": ["test_cleaning", "test_relationships"],
    "Analysis": ["test_metrics", "test_filters_and_exports"],
    "Application": ["test_charts", "test_app", "test_repo_hygiene"],
}


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    tail = (result.stdout + result.stderr).strip().splitlines()[-1:] or [""]
    return result.returncode, tail[0]


def junit_counts(path: Path) -> dict[str, dict[str, int]]:
    """Passed and failed test counts by test module, from a JUnit XML file."""
    out: dict[str, dict[str, int]] = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        module = case.attrib["classname"].split(".")[1]
        entry = out.setdefault(module, {"passed": 0, "failed": 0, "skipped": 0})
        if case.find("failure") is not None or case.find("error") is not None:
            entry["failed"] += 1
        elif case.find("skipped") is not None:
            entry["skipped"] += 1
        else:
            entry["passed"] += 1
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true", help="also run the Playwright tests")
    args = parser.parse_args()

    steps = {}
    steps["inspect"] = run([PY, "scripts/inspect_sources.py"])
    steps["build"] = run([PY, "scripts/build_data.py"])
    before = {p.name: sha(p) for p in (ROOT / "data" / "processed").glob("*.csv")}
    steps["rebuild"] = run([PY, "scripts/build_data.py"])
    after = {p.name: sha(p) for p in (ROOT / "data" / "processed").glob("*.csv")}
    deterministic = before == after and len(before) == 2
    steps["lint"] = run([PY, "-m", "ruff", "check", "."])
    steps["format"] = run([PY, "-m", "ruff", "format", "--check", "."])
    steps["tests"] = run([PY, "-m", "pytest", "-q"])
    counts = junit_counts(REPORTS / "pytest_junit.xml")
    browser = None
    if args.browser:
        steps["browser"] = run(
            [
                PY,
                "-m",
                "pytest",
                "-m",
                "browser",
                "-q",
                "--junitxml=reports/pytest_junit_browser.xml",
            ]
        )
        browser = junit_counts(REPORTS / "pytest_junit_browser.xml")

    def total(modules, key):
        return sum(counts.get(m, {}).get(key, 0) for m in modules)

    def area_status(area):
        modules = AREA_FILES[area]
        ok = total(modules, "failed") == 0 and total(modules, "passed") > 0
        return "PASS" if ok else "FAIL"

    all_passed = sum(v["passed"] for v in counts.values())
    all_failed = sum(v["failed"] for v in counts.values())
    all_skipped = sum(v["skipped"] for v in counts.values())
    rows = []
    for area, title in (
        ("Source files", "Workbooks parse and match the recorded snapshot."),
        ("Cleaning and integrity", "Identifiers, joins, types and the change log."),
        ("Analysis", "Counts and shares recomputed independently; filters and exports."),
        ("Application", "Charts, Streamlit app behaviour and repository checks."),
    ):
        modules = ", ".join(AREA_FILES[area])
        rows.append(
            (
                area,
                area_status(area),
                f"python -m pytest -q ({modules})",
                f"{total(AREA_FILES[area], 'passed')} passed, "
                f"{total(AREA_FILES[area], 'failed')} failed",
                title,
            )
        )
    tests_status = "PASS" if (all_failed == 0 and steps["tests"][0] == 0) else "FAIL"
    tests_note = "Browser tests not run."
    if browser is not None:
        b_pass = sum(v["passed"] for v in browser.values())
        b_fail = sum(v["failed"] for v in browser.values())
        tests_status = "PASS" if tests_status == "PASS" and b_fail == 0 and b_pass > 0 else "FAIL"
        tests_note = f"Playwright: {b_pass} passed, {b_fail} failed."
    rows.append(
        (
            "Functional and browser tests",
            tests_status,
            "python -m pytest -q; python -m pytest -m browser",
            f"{all_passed} passed, {all_failed} failed, {all_skipped} skipped",
            tests_note,
        )
    )
    readme = (
        (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    )
    shot = ROOT / "screenshots" / "streamlit_dashboard.png"
    docs_status = (
        "PASS" if shot.exists() and "Placeholder" not in readme and len(readme) > 500 else "FAIL"
    )
    rows.append(
        (
            "Documentation",
            docs_status,
            "file checks",
            f"screenshot present: {shot.exists()}; README present: "
            f"{'Placeholder' not in readme and len(readme) > 500}",
            "Licence position recorded in data/README.md.",
        )
    )
    repro_status = (
        "PASS"
        if (
            all(code == 0 for code, _ in steps.values())
            and deterministic
            and tests_status == "PASS"
        )
        else "FAIL"
    )
    rows.append(
        (
            "Reproduction",
            repro_status,
            "inspect, build twice, ruff, pytest" + (", browser" if args.browser else ""),
            f"rebuild byte-identical: {deterministic}; exit codes: "
            + ", ".join(f"{k}={v[0]}" for k, v in steps.items()),
            "Environment: see manual review.",
        )
    )

    lines = [
        "# Verification report",
        "",
        "Generated by `scripts/write_verification.py`.",
        "",
        "| Area | Status | Command | Evidence | Notes |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {g} | {s} | {c} | {e} | {n} |" for g, s, c, e, n in rows]
    lines += [
        "",
        "## Test counts by module",
        "",
        "| Module | Passed | Failed | Skipped |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f"| {m} | {v['passed']} | {v['failed']} | {v['skipped']} |"
        for m, v in sorted(counts.items())
    ]
    manual = REPORTS / "manual_review.md"
    if manual.exists():
        lines += ["", manual.read_text(encoding="utf-8").strip()]
    (REPORTS / "verification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[4 : 4 + len(rows) + 2]))
    return 0 if all(r[1] == "PASS" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
