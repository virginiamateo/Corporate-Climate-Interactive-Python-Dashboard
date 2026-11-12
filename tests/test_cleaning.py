"""Deterministic cleaning, with every transformation logged and counted."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from climate_targets import clean, datasets

# ---- Pure function behaviour (input validation, no records are created or stored) ----


@pytest.mark.parametrize(
    "value",
    [40023788.0, "4.0023788E7", "40023788", 40023788, " 40023788 ", "40023788.0"],
)
def test_normalize_sbti_id_accepts_exact_integral_values(value):
    assert clean.normalize_sbti_id(value) == "40023788"


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "  ",
        40023788.5,
        30023788.0,
        400237881.0,
        4002378.0,
        "abc",
        float("nan"),
        float("inf"),
        True,
        -40023788.0,
        [40023788],
    ],
)
def test_normalize_sbti_id_rejects_invalid_values(value):
    with pytest.raises(clean.IdError):
        clean.normalize_sbti_id(value)


def test_normalize_year():
    assert clean.normalize_year(2030.0) == ("2030", True)
    assert clean.normalize_year("2030") == ("2030", False)
    assert clean.normalize_year("FY2030") == ("FY2030", False)
    assert clean.normalize_year("") == ("", False)
    assert clean.normalize_year("NA") == ("NA", False)
    with pytest.raises(ValueError):
        clean.normalize_year(2030.5)


def test_normalize_scope():
    assert clean.normalize_scope(1.0) == ("1", True)
    assert clean.normalize_scope(3.0) == ("3", True)
    assert clean.normalize_scope("1+2") == ("1+2", False)
    assert clean.normalize_scope("1+2+3") == ("1+2+3", False)
    assert clean.normalize_scope("NA") == ("NA", False)
    with pytest.raises(ValueError):
        clean.normalize_scope(4.0)


def test_normalize_date_handles_datetimes_and_excel_serials():
    assert clean.normalize_date(dt.datetime(2025, 9, 18, 1, 0)) == ("2025-09-18", True)
    assert clean.normalize_date(45000) == ("2023-03-15", True)  # Excel serial, 1899-12-30 origin
    assert clean.normalize_date("NA") == ("NA", False)
    assert clean.normalize_date("") == ("", False)
    for bad in (0, -5, 1e9, float("nan")):
        with pytest.raises(ValueError):
            clean.normalize_date(bad)


def test_target_year_number_removes_fy_prefix():
    out = clean.target_year_number(pd.Series(["2030", "FY2030", "CY2031", "", "NA"]))
    assert out.tolist()[:3] == [2030, 2030, 2031]
    assert out.isna().tolist() == [False, False, False, True, True]


# ---- Behaviour on the real workbooks ----


@pytest.mark.data
def test_row_counts_preserved(raw_frames, cleaned):
    assert len(cleaned["companies"]) == len(raw_frames["companies"])
    assert len(cleaned["targets"]) == len(raw_frames["targets"])


@pytest.mark.data
def test_raw_frames_are_not_modified_by_cleaning(raw_frames, cleaned):
    assert raw_frames["companies"]["sbti_id"].map(type).eq(float).all()
    assert "sbti_id_raw" not in raw_frames["companies"].columns


@pytest.mark.data
@pytest.mark.parametrize("table", ["companies", "targets"])
def test_blank_and_literal_na_counts_are_unchanged(table, raw_frames, cleaned):
    raw, out = raw_frames[table], cleaned[table]
    for column in raw.columns:
        assert (raw[column] == "").sum() == (out[column] == "").sum(), column
        assert (raw[column] == "NA").sum() == (out[column] == "NA").sum(), column


@pytest.mark.data
def test_every_cleaned_cell_is_text_and_none_is_left(cleaned):
    for table in ("companies", "targets"):
        frame = cleaned[table]
        assert not frame.isna().any().any()
        assert all(frame[c].map(type).eq(str).all() for c in frame.columns)


@pytest.mark.data
def test_sbti_ids_are_eight_digit_text_and_match_independent_ids(companies, targets):
    assert companies["sbti_id"].str.fullmatch(r"4\d{7}").all()
    assert targets["sbti_id"].str.fullmatch(r"4\d{7}").all()
    assert (
        companies["sbti_id_raw"].astype(float).astype(int).astype(str) == companies["sbti_id"]
    ).all()


@pytest.mark.data
@pytest.mark.snapshot
def test_integer_like_target_years_are_normalised(raw_frames, targets, reference):
    raw = raw_frames["targets"]
    float_rows = raw["target_year"].map(lambda v: isinstance(v, float))
    assert float_rows.sum() == reference["target_year_float_cells"] == 41
    cleaned_values = targets.set_index("row_entry_id").loc[
        raw.loc[float_rows, "row_entry_id"], "target_year"
    ]
    assert cleaned_values.str.fullmatch(r"\d{4}").all()
    assert targets["target_year"].str.contains(r"\.").sum() == 0


@pytest.mark.data
def test_fy_prefix_is_kept_in_company_year_columns(raw_frames, companies):
    raw_fy = (
        raw_frames["companies"]["near_term_target_year"]
        .map(lambda v: isinstance(v, str) and v.startswith("FY"))
        .sum()
    )
    assert raw_fy > 0
    assert companies["near_term_target_year"].str.startswith("FY").sum() == raw_fy


@pytest.mark.data
@pytest.mark.snapshot
def test_scope_mapping_preserves_multi_scope_values(raw_frames, targets, reference):
    raw = raw_frames["targets"]["scope"]
    assert raw.map(lambda v: isinstance(v, float)).sum() == reference["scope_float_cells"]
    assert set(targets["scope"].unique()) <= {
        "",
        "NA",
        "1",
        "2",
        "3",
        "1+2",
        "1+3",
        "2+3",
        "1+2+3",
    } | set(raw[raw.map(lambda v: isinstance(v, str))])
    for multi in ("1+2", "1+2+3"):
        assert (raw == multi).sum() == (targets["scope"] == multi).sum() > 0
    assert (targets["scope_raw"].isin(["1.0", "2.0", "3.0"])).sum() == reference[
        "scope_float_cells"
    ]


@pytest.mark.data
def test_dates_are_iso_and_span_a_plausible_range(companies, targets, reference):
    for frame, column in ((companies, "date_updated"), (targets, "date_published")):
        assert frame[column].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert companies["date_updated"].min() == reference["company_min_date_updated"]
    assert companies["date_updated"].max() == reference["company_max_date_updated"]
    assert targets["date_published"].max() <= dt.date.today().isoformat()


@pytest.mark.data
def test_a_sampled_source_cell_matches_its_cleaned_date(raw_frames, companies):
    raw = raw_frames["companies"]
    row = raw.iloc[0]
    assert isinstance(row["date_updated"], dt.datetime)
    cleaned_value = companies.set_index("sbti_id_raw").loc[str(row["sbti_id"]), "date_updated"]
    assert cleaned_value == row["date_updated"].date().isoformat()


@pytest.mark.data
def test_whitespace_is_stripped_only_from_key_columns(raw_frames, targets):
    raw = raw_frames["targets"]
    assert targets["company_name"].map(lambda v: v == v.strip()).all()
    # free text is left exactly as in the source
    original = raw.set_index("row_entry_id")["target_wording"].astype(str)
    cleaned_text = targets.set_index("row_entry_id")["target_wording"]
    assert (original.loc[cleaned_text.index] == cleaned_text).all()


@pytest.mark.data
def test_change_log_counts_match_independent_recounts(raw_frames, cleaned):
    log = {(c.rule, c.table, c.column): c for c in cleaned["log"]}
    raw_t, raw_c = raw_frames["targets"], raw_frames["companies"]

    def count(series, predicate):
        return int(series.map(predicate).sum())

    is_float = lambda v: isinstance(v, float)  # noqa: E731
    is_dt = lambda v: isinstance(v, dt.datetime)  # noqa: E731

    assert log["normalize_year", "targets", "target_year"].changed == count(
        raw_t["target_year"], is_float
    )
    assert log["normalize_year", "targets", "base_year"].changed == count(
        raw_t["base_year"], is_float
    )
    assert log["normalize_scope", "targets", "scope"].changed == count(raw_t["scope"], is_float)
    assert log["normalize_date", "companies", "date_updated"].changed == count(
        raw_c["date_updated"], is_dt
    )
    assert log["normalize_date", "targets", "commitment_deadline"].changed == count(
        raw_t["commitment_deadline"], is_dt
    )
    assert log["normalize_sbti_id", "companies", "sbti_id"].changed == len(raw_c)
    stripped = count(raw_t["company_name"], lambda v: v != v.strip())
    assert log["strip_whitespace", "targets", "company_name"].changed == stripped == 5
    assert log["strip_whitespace", "companies", "company_name"].changed == count(
        raw_c["company_name"], lambda v: v != v.strip()
    )
    for entry in cleaned["log"]:
        assert entry.examined == len(cleaned[entry.table])
        assert 0 <= entry.changed <= entry.examined


@pytest.mark.data
def test_no_unrecognised_year_values(cleaned):
    flags = [c for c in cleaned["log"] if c.rule == "flag_unrecognised_year"]
    assert flags
    assert all(c.note.startswith("0 values") for c in flags)


@pytest.mark.data
@pytest.mark.parametrize("table", ["companies", "targets"])
def test_processed_csv_equals_cleaned_frame(table, cleaned, processed):
    """Round trip through CSV preserves every value, including blank versus NA."""
    pd.testing.assert_frame_equal(cleaned[table], processed[table], check_dtype=True)


@pytest.mark.data
def test_processed_loader_keeps_na_literal_distinct_from_blank(processed):
    t = processed["targets"]
    assert (t["commitment_type"] == "NA").sum() > 0
    assert (t["commitment_type"] == "").sum() > 0
    assert not t.isna().any().any()


def test_missing_processed_file_gives_a_clear_error(tmp_path):
    with pytest.raises(datasets.DataNotBuiltError, match="build_data.py"):
        datasets.read_processed(tmp_path / "companies.csv")
