"""The original workbooks are present, parseable and as documented."""

from __future__ import annotations

import json

import openpyxl
import pytest

from climate_targets import config, ingest

pytestmark = pytest.mark.data


def test_raw_files_exist():
    for path in (config.COMPANIES_XLSX, config.TARGETS_XLSX, config.DICTIONARY_XLSX):
        assert path.exists(), path


def test_expected_worksheets_exist():
    assert config.COMPANIES_SHEET in ingest.sheet_names(config.COMPANIES_XLSX)
    assert config.TARGETS_SHEET in ingest.sheet_names(config.TARGETS_XLSX)


def test_data_dictionary_opens_with_seven_worksheets():
    dictionary = ingest.read_dictionary(config.DICTIONARY_XLSX)
    assert len(dictionary) == 7
    assert all(not frame.empty for frame in dictionary.values())


def test_column_names_are_exactly_the_documented_ones(raw_frames):
    assert list(raw_frames["companies"].columns) == config.COMPANY_COLUMNS
    assert list(raw_frames["targets"].columns) == config.TARGET_COLUMNS


def test_trailing_company_columns_are_blank_before_being_dropped():
    """Read the worksheet directly and confirm every headerless column is empty."""
    workbook = openpyxl.load_workbook(config.COMPANIES_XLSX, read_only=True, data_only=True)
    rows = workbook[config.COMPANIES_SHEET].iter_rows(values_only=True)
    header = next(rows)
    unnamed = [i for i, name in enumerate(header) if name is None]
    assert len(unnamed) == 4
    for row in rows:
        for i in unnamed:
            assert i >= len(row) or row[i] in (None, "")
    workbook.close()


def test_reader_rejects_a_headerless_column_that_contains_values(tmp_path):
    """Error handling: a workbook with a stray value in an unnamed column must not load."""
    path = tmp_path / "stray.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["a", "b", None])
    sheet.append([1, 2, "stray"])
    workbook.save(path)
    with pytest.raises(ValueError, match="no header"):
        ingest.read_sheet(path, "Data")


def test_worksheet_widths(raw_frames, reference):
    assert raw_frames["widths"] == (
        reference["companies_worksheet_width"],
        reference["targets_worksheet_width"],
    )
    assert len(raw_frames["companies"].columns) == 22
    assert len(raw_frames["targets"].columns) == 28


@pytest.mark.snapshot
def test_hashes_match_reference_snapshot(reference):
    """The ``reference`` fixture fails with an explanatory message if any hash differs."""
    assert set(reference["hashes"]) == {
        "companies-excel.xlsx",
        "targets-excel.xlsx",
        "Alpha-Dashboard-Data-Dictionary.xlsx",
    }


@pytest.mark.snapshot
def test_reference_file_matches_a_fresh_independent_recount(reference, live_recount):
    """Guards against a stale or hand-edited reference file."""
    assert reference == live_recount


@pytest.mark.snapshot
def test_source_row_counts(raw_frames, reference):
    assert len(raw_frames["companies"]) == reference["company_rows"]
    assert len(raw_frames["targets"]) == reference["target_rows"]


def test_manifest_matches_files():
    manifest = json.loads((config.REPORTS_DIR / "source_manifest.json").read_text())
    for path in (config.COMPANIES_XLSX, config.TARGETS_XLSX, config.DICTIONARY_XLSX):
        entry = manifest["files"][path.name]
        assert entry["sha256"] == ingest.sha256_file(path)
        assert entry["bytes"] == path.stat().st_size
    assert manifest["files"]["companies-excel.xlsx"]["data_rows"] > 0
