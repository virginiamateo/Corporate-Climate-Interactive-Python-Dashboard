"""Build data/processed/companies.csv and targets.csv from the raw workbooks.

Also writes reports/data_quality.json and reports/eda_summary.json.
The build stops without writing outputs if any integrity check fails.
"""

from __future__ import annotations

import json
import sys

from climate_targets import analysis, clean, config, datasets, ingest, validate


def main() -> int:
    for path in (config.COMPANIES_XLSX, config.TARGETS_XLSX):
        if not path.exists():
            print(f"{path} not found. See data/README.md for the download links.")
            return 2

    raw_companies, company_width = ingest.read_sheet(config.COMPANIES_XLSX, config.COMPANIES_SHEET)
    raw_targets, target_width = ingest.read_sheet(config.TARGETS_XLSX, config.TARGETS_SHEET)

    companies, company_log = clean.clean_companies(raw_companies)
    targets, target_log = clean.clean_targets(raw_targets)

    if len(companies) != len(raw_companies) or len(targets) != len(raw_targets):
        print("FAIL: row count changed during cleaning")
        return 1

    checks = validate.run_all_checks(companies, targets)
    failed = [c for c in checks if not c.passed]
    for check in checks:
        print(
            f"{'PASS' if check.passed else 'FAIL'}  {check.name}: {check.count} "
            f"(expected {check.expected})"
        )
    if failed:
        print("FAIL: integrity checks failed, nothing written")
        return 1

    datasets.write_processed(companies, config.COMPANIES_CSV)
    datasets.write_processed(targets, config.TARGETS_CSV)

    log = [c.as_dict() for c in company_log + target_log]
    report = {
        "tables": {
            "companies": {
                "raw_rows": len(raw_companies),
                "raw_worksheet_columns": company_width,
                "raw_named_fields": len(raw_companies.columns),
                "processed_rows": len(companies),
                "processed_columns": len(companies.columns),
                "note": (
                    "Four trailing worksheet columns have no header and no values and were dropped."
                    if company_width > len(raw_companies.columns)
                    else ""
                ),
            },
            "targets": {
                "raw_rows": len(raw_targets),
                "raw_worksheet_columns": target_width,
                "raw_named_fields": len(raw_targets.columns),
                "processed_rows": len(targets),
                "processed_columns": len(targets.columns),
                "note": "",
            },
        },
        "checks": [c.as_dict() for c in checks],
        "change_log": log,
        "values_changed_total": sum(entry["changed"] for entry in log),
        "missingness": {
            "companies": validate.missingness(companies).to_dict("records"),
            "targets": validate.missingness(targets).to_dict("records"),
        },
    }
    config.REPORTS_DIR.mkdir(exist_ok=True)
    (config.REPORTS_DIR / "data_quality.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    summary = analysis.get_eda_summary(
        companies,
        targets,
        {
            "raw_rows": {"companies": len(raw_companies), "targets": len(raw_targets)},
            "raw_named_fields": {
                "companies": len(raw_companies.columns),
                "targets": len(raw_targets.columns),
            },
        },
    )
    (config.REPORTS_DIR / "eda_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {config.COMPANIES_CSV.name} ({len(companies):,} rows) and "
        f"{config.TARGETS_CSV.name} ({len(targets):,} rows)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
