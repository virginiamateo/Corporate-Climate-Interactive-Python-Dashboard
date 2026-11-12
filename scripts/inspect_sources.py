"""Describe the three SBTi workbooks and write reports/source_manifest.json.

Also writes the source section of reports/source_audit.md. Nothing is modified in data/raw.
"""

from __future__ import annotations

import datetime as dt
import json
import sys

from climate_targets import config, ingest

MANIFEST = config.REPORTS_DIR / "source_manifest.json"
AUDIT = config.REPORTS_DIR / "source_audit.md"


def describe_table(path, sheet):
    frame, width = ingest.read_sheet(path, sheet)
    dates = (
        [v for v in frame["date_updated"] if isinstance(v, dt.datetime)]
        if ("date_updated" in frame.columns)
        else []
    )
    out = {
        "worksheet": sheet,
        "data_rows": len(frame),
        "named_fields": len(frame.columns),
        "worksheet_columns": width,
        "columns": list(frame.columns),
    }
    if dates:
        out["max_date_updated"] = max(dates).date().isoformat()
    return out


def main() -> int:
    missing = [
        p.name
        for p in (config.COMPANIES_XLSX, config.TARGETS_XLSX, config.DICTIONARY_XLSX)
        if not p.exists()
    ]
    if missing:
        print(f"Missing {missing} in {config.RAW_DIR}. See data/README.md for the download links.")
        return 2

    files = {}
    for path in (config.COMPANIES_XLSX, config.TARGETS_XLSX, config.DICTIONARY_XLSX):
        stat = path.stat()
        files[path.name] = {
            "official_url": config.SOURCE_URLS[path.name],
            "bytes": stat.st_size,
            "sha256": ingest.sha256_file(path),
            "worksheets": ingest.sheet_names(path),
        }
    files[config.COMPANIES_XLSX.name].update(
        describe_table(config.COMPANIES_XLSX, config.COMPANIES_SHEET)
    )
    files[config.TARGETS_XLSX.name].update(
        describe_table(config.TARGETS_XLSX, config.TARGETS_SHEET)
    )

    dictionary = ingest.read_dictionary(config.DICTIONARY_XLSX)
    files[config.DICTIONARY_XLSX.name]["worksheet_shapes"] = {
        name: list(frame.shape) for name, frame in dictionary.items()
    }

    manifest = {
        "source_page": config.SOURCE_PAGE,
        "note": (
            "max_date_updated is the latest company record update in the file and is not the "
            "workbook publication date."
        ),
        "files": files,
    }
    config.REPORTS_DIR.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    co = files[config.COMPANIES_XLSX.name]
    ta = files[config.TARGETS_XLSX.name]
    lines = [
        "# Source file audit",
        "",
        "## Source files",
        "",
        "Written by `scripts/inspect_sources.py`. Values are read directly from the files.",
        "",
        "| File | Worksheet | Data rows | Named fields | Worksheet columns | Bytes | SHA-256 |",
        "|---|---|---:|---:|---:|---:|---|",
        f"| companies-excel.xlsx | {co['worksheet']} | {co['data_rows']:,} | {co['named_fields']} "
        f"| {co['worksheet_columns']} | {co['bytes']:,} | `{co['sha256']}` |",
        f"| targets-excel.xlsx | {ta['worksheet']} | {ta['data_rows']:,} | {ta['named_fields']} "
        f"| {ta['worksheet_columns']} | {ta['bytes']:,} | `{ta['sha256']}` |",
        f"| Alpha-Dashboard-Data-Dictionary.xlsx "
        f"| {len(files[config.DICTIONARY_XLSX.name]['worksheets'])} "
        f"worksheets | not applicable | not applicable | not applicable | "
        f"{files[config.DICTIONARY_XLSX.name]['bytes']:,} | "
        f"`{files[config.DICTIONARY_XLSX.name]['sha256']}` |",
        "",
        f"Maximum company `date_updated`: {co.get('max_date_updated')}. This is not the workbook "
        "publication date.",
        "",
    ]
    AUDIT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {MANIFEST.relative_to(config.ROOT)} and {AUDIT.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
