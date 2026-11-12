"""Data quality and methodology tab. Everything shown is read from reports written by the
pipeline or recomputed from the loaded data."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import streamlit as st

from .. import config, validate
from ..formatting import fmt_int
from ..theme import style_result_column

GLOSSARY = {
    "Registered company": "A company with a record in the SBTi companies file, identified by "
    "its SBTi ID. The company table has one row per registered company.",
    "Target record": "One row of the targets file: a single target or commitment of a company. "
    "A company can have several, so records are not companies.",
    "Commitment": "A company's commitment to set a target. It is not a validated target.",
    "Validated target": "A target that SBTi has validated. Validation is not evidence that "
    "emissions have fallen.",
    "Removed commitment": "A commitment that SBTi lists as removed, for example when a "
    "deadline expired.",
    "Not recorded": "The source cell is blank. For net-zero status this means no status is "
    "recorded. It is not read as a failed or removed commitment.",
    "Share denominator": "Every share is the number of registered companies in the filtered "
    "group. Target records are never used as a denominator for company shares.",
}


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_junit(path: Path) -> dict | None:
    """Totals from a pytest JUnit XML file, or None if it does not exist."""
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    attrs = suite.attrib
    return {
        "tests": int(attrs["tests"]), "failures": int(attrs["failures"]),
        "errors": int(attrs["errors"]), "skipped": int(attrs["skipped"]),
        "timestamp": attrs.get("timestamp", ""),
    }  # fmt: skip


def render(checks: list[validate.CheckResult], reports_dir: Path = config.REPORTS_DIR) -> None:
    st.header("Data quality and methodology", anchor=False)
    quality = read_json(reports_dir / "data_quality.json")
    manifest = read_json(reports_dir / "source_manifest.json")
    if quality is None or manifest is None:
        st.info(
            "Reports not found. Run python scripts/inspect_sources.py and "
            "python scripts/build_data.py to create them."
        )
        return

    st.subheader("Raw and processed tables", anchor=False)
    tables = pd.DataFrame(
        [
            {
                "Table": name,
                "Raw rows": t["raw_rows"],
                "Processed rows": t["processed_rows"],
                "Raw named fields": t["raw_named_fields"],
                "Raw worksheet columns": t["raw_worksheet_columns"],
                "Processed columns": t["processed_columns"],
            }
            for name, t in quality["tables"].items()
        ]
    )
    st.dataframe(tables, hide_index=True, width="stretch")
    st.caption(
        "The companies worksheet has four trailing columns without a header and without values. "
        "They were dropped after checking that every cell is empty. Processed tables also carry "
        "the original values of transformed columns in columns ending in _raw."
    )

    st.subheader("Identifier and join checks", anchor=False)
    checks_table = pd.DataFrame(
        [
            {
                "Check": c.description,
                "Count": c.count,
                "Expected": c.expected,
                "Result": "Pass" if c.passed else "Fail",
            }
            for c in checks
        ]
    )
    st.dataframe(style_result_column(checks_table), hide_index=True, width="stretch")

    st.subheader("Transformations", anchor=False)
    log = pd.DataFrame(quality["change_log"])
    shown = log[log["changed"] > 0][["table", "column", "rule", "examined", "changed", "note"]]
    st.dataframe(shown, hide_index=True, width="stretch")
    st.caption(
        f"{fmt_int(quality['values_changed_total'])} cell values were changed in total across "
        "both tables. Rows examined equals the table row count. No rows were removed or imputed."
    )

    st.subheader("Missing values", anchor=False)
    st.markdown(
        "A blank cell and the literal text `NA` are counted separately. On commitment records the "
        "target-specific fields (scope, target year, target value) are structurally empty, and a "
        "blank company net-zero status means no status is recorded."
    )
    c1, c2 = st.columns(2)
    for col, name in ((c1, "companies"), (c2, "targets")):
        frame = pd.DataFrame(quality["missingness"][name]).sort_values(
            ["blank_pct", "na_literal_pct"], ascending=False
        )
        frame = frame[(frame["blank"] > 0) | (frame["na_literal"] > 0)][
            ["column", "blank", "blank_pct", "na_literal", "na_literal_pct"]
        ]
        col.markdown(f"**{name.capitalize()} table**")
        col.dataframe(frame, hide_index=True, width="stretch")

    st.subheader("Source files", anchor=False)
    files = pd.DataFrame(
        [
            {
                "File": name,
                "Worksheets": ", ".join(f["worksheets"]),
                "Bytes": f["bytes"],
                "SHA-256": f["sha256"],
            }
            for name, f in manifest["files"].items()
        ]
    )
    st.dataframe(files, hide_index=True, width="stretch")
    latest = manifest["files"]["companies-excel.xlsx"].get("max_date_updated", "unknown")
    st.markdown(
        f"- Latest company `date_updated` in the file: **{latest}**\n"
        f"- Source page: {manifest['source_page']}"
    )
    st.caption(
        "The latest update date is not the workbook publication date. The original download "
        "time is not recorded, and SBTi may refresh the files at the same addresses."
    )

    junit = read_junit(reports_dir / "pytest_junit.xml")
    if junit is not None:
        st.subheader("Automated test run", anchor=False)
        passed = junit["tests"] - junit["failures"] - junit["errors"] - junit["skipped"]
        st.markdown(
            f"Last run recorded in `reports/pytest_junit.xml`: **{passed} passed** of "
            f"{junit['tests']} tests, {junit['failures']} failed, {junit['errors']} errors, "
            f"{junit['skipped']} skipped ."
        )

    st.subheader("Glossary", anchor=False)
    for term, text in GLOSSARY.items():
        st.markdown(f"**{term}.** {text}")
