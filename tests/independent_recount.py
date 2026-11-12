"""Recount the headline figures straight from the SBTi workbooks.

This module deliberately imports nothing from ``climate_targets``. It uses only the standard
library and ``openpyxl`` so that it is an independent check on the production pipeline.

Run ``python tests/independent_recount.py`` to regenerate the reference file in
``tests/reference_values/``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REFERENCE_DIR = ROOT / "tests" / "reference_values"

FILES = {
    "companies": (RAW / "companies-excel.xlsx", "Data"),
    "targets": (RAW / "targets-excel.xlsx", "WebsiteData"),
}
DICTIONARY = RAW / "Alpha-Dashboard-Data-Dictionary.xlsx"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rows(path: Path, sheet: str):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook[sheet].iter_rows(values_only=True)
        header = next(rows)
        named = [(i, h) for i, h in enumerate(header) if h is not None]
        out = [{h: (row[i] if i < len(row) else None) for i, h in named} for row in rows]
        return [h for _, h in named], len(header), out
    finally:
        workbook.close()


def _id(value) -> int:
    assert float(value) == int(value), value
    return int(value)


def _group_table(companies: list[dict], key: str) -> dict:
    table: dict[str, dict] = {}
    for row in companies:
        group = table.setdefault(
            row[key], {"companies": 0, "near_term_validated": 0, "net_zero_validated": 0}
        )
        group["companies"] += 1
        group["near_term_validated"] += row["near_term_status"] == "Validated Targets"
        group["net_zero_validated"] += row["net_zero_status"] == "Validated Targets"
    return dict(sorted(table.items()))


def recount() -> dict:
    c_cols, c_width, companies = _rows(*FILES["companies"])
    t_cols, t_width, targets = _rows(*FILES["targets"])

    company_ids = [_id(r["sbti_id"]) for r in companies]
    target_company_ids = [_id(r["sbti_id"]) for r in targets]
    row_ids = [r["row_entry_id"] for r in targets]
    known = set(company_ids)
    linked = set(target_company_ids)

    def blank(v):
        return v in (None, "")

    near = Counter(r["near_term_status"] for r in companies)
    net = Counter(
        "(blank)" if blank(r["net_zero_status"]) else r["net_zero_status"] for r in companies
    )
    dates = [r["date_updated"] for r in companies if isinstance(r["date_updated"], dt.datetime)]

    return {
        "hashes": {
            "companies-excel.xlsx": _sha256(FILES["companies"][0]),
            "targets-excel.xlsx": _sha256(FILES["targets"][0]),
            "Alpha-Dashboard-Data-Dictionary.xlsx": _sha256(DICTIONARY),
        },
        "companies_columns": c_cols,
        "targets_columns": t_cols,
        "companies_worksheet_width": c_width,
        "targets_worksheet_width": t_width,
        "company_rows": len(companies),
        "target_rows": len(targets),
        "distinct_company_ids": len(known),
        "distinct_row_entry_ids": len(set(row_ids)),
        "distinct_locations": len({r["location"] for r in companies}),
        "distinct_sectors": len({r["sector"] for r in companies}),
        "distinct_regions": len({r["region"] for r in companies}),
        "distinct_organization_types": len({r["organization_type"] for r in companies}),
        "orphan_target_records": sum(1 for i in target_company_ids if i not in known),
        "companies_without_targets": len(known - linked),
        "row_entry_id_suffix_mismatches": sum(
            1
            for rid, i in zip(row_ids, target_company_ids, strict=True)
            if int(rid.rsplit("-", 1)[1]) != i
        ),
        "near_term_status": dict(near),
        "net_zero_status": dict(net),
        "target_action": dict(Counter(r["action"] for r in targets)),
        "target_status_other_rows": sum(1 for r in targets if r["status"] == "Other"),
        "target_year_float_cells": sum(isinstance(r["target_year"], float) for r in targets),
        "base_year_float_cells": sum(isinstance(r["base_year"], float) for r in targets),
        "scope_float_cells": sum(isinstance(r["scope"], float) for r in targets),
        "company_net_zero_blank": sum(blank(r["net_zero_status"]) for r in companies),
        "company_max_date_updated": max(dates).date().isoformat(),
        "company_min_date_updated": min(dates).date().isoformat(),
        "target_min_date_published": min(
            r["date_published"] for r in targets if isinstance(r["date_published"], dt.datetime)
        )
        .date()
        .isoformat(),
        "target_max_date_published": max(
            r["date_published"] for r in targets if isinstance(r["date_published"], dt.datetime)
        )
        .date()
        .isoformat(),
        "by_location": _group_table(companies, "location"),
        "by_sector": _group_table(companies, "sector"),
        "by_organization_type": _group_table(companies, "organization_type"),
    }


def write_reference() -> Path:
    data = recount()
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = REFERENCE_DIR / "snapshot.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write_reference())
    sys.exit(0)
