"""Shared fixtures, markers and the raw-data guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from climate_targets import clean, config, datasets, ingest

REFERENCE_FILE = Path(__file__).parent / "reference_values" / "snapshot.json"
RAW_FILES = [config.COMPANIES_XLSX, config.TARGETS_XLSX, config.DICTIONARY_XLSX]


def pytest_addoption(parser):
    parser.addoption(
        "--no-data",
        action="store_true",
        help="Deselect tests that need the raw SBTi workbooks (used by CI only).",
    )


def _missing_raw() -> list[str]:
    return [p.name for p in RAW_FILES if not p.exists()]


DATA_FIXTURES = {
    "raw_frames",
    "cleaned",
    "companies",
    "targets",
    "processed",
    "reference",
    "live_recount",
}


def pytest_collection_modifyitems(config, items):
    """Mark every test that uses a data fixture as ``data``; drop them under --no-data."""
    for item in items:
        if DATA_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.data)
    if not config.getoption("--no-data"):
        return
    kept, dropped = [], []
    for item in items:
        (dropped if "data" in item.keywords else kept).append(item)
    items[:] = kept
    config.hook.pytest_deselected(items=dropped)
    print(
        f"\n--no-data: {len(dropped)} tests that need the raw workbooks were deselected. "
        "This run is not full verification."
    )


@pytest.fixture(autouse=True)
def _raw_data_guard(request):
    """Tests marked ``data`` fail with a clear message if the raw workbooks are absent."""
    if "data" in request.keywords:
        missing = _missing_raw()
        if missing:
            pytest.fail(
                f"Raw files missing from data/raw: {missing}. "
                "See data/README.md for the download links.",
                pytrace=False,
            )


@pytest.fixture(scope="session")
def reference() -> dict:
    """Recounted reference values, valid only for the workbooks they were recounted from."""
    data = json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))
    live = {p.name: ingest.sha256_file(p) for p in RAW_FILES if p.exists()}
    if live != data["hashes"]:
        pytest.fail(
            "The workbooks in data/raw differ from the snapshot in "
            f"{REFERENCE_FILE.name}. Run tests/independent_recount.py, review the differences, "
            "then update the reference file deliberately.",
            pytrace=False,
        )
    return data


@pytest.fixture(scope="session")
def live_recount() -> dict:
    import independent_recount

    return independent_recount.recount()


@pytest.fixture(scope="session")
def raw_frames():
    companies, c_width = ingest.read_sheet(config.COMPANIES_XLSX, config.COMPANIES_SHEET)
    targets, t_width = ingest.read_sheet(config.TARGETS_XLSX, config.TARGETS_SHEET)
    return {"companies": companies, "targets": targets, "widths": (c_width, t_width)}


@pytest.fixture(scope="session")
def cleaned(raw_frames):
    companies, c_log = clean.clean_companies(raw_frames["companies"])
    targets, t_log = clean.clean_targets(raw_frames["targets"])
    return {"companies": companies, "targets": targets, "log": c_log + t_log}


@pytest.fixture(scope="session")
def companies(cleaned):
    return cleaned["companies"]


@pytest.fixture(scope="session")
def targets(cleaned):
    return cleaned["targets"]


@pytest.fixture(scope="session")
def processed():
    """The processed CSV files as the app reads them."""
    return {"companies": datasets.load_companies(), "targets": datasets.load_targets()}
