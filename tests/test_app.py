"""The Streamlit app runs, its controls work and it shows the recounted numbers."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from climate_targets import analysis, config, datasets
from climate_targets.formatting import fmt_int, fmt_pct

pytestmark = [pytest.mark.app, pytest.mark.data]

UK = "United Kingdom of Great Britain and Northern Ireland"
APP = str(config.ROOT / "app.py")


@pytest.fixture
def app(processed) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    return at


def _metrics(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


def _captions(at: AppTest) -> list[str]:
    return [c.value for c in at.caption]


def _select(at: AppTest, label: str):
    return next(w for w in at.sidebar.multiselect if w.label == label)


def test_app_runs_and_shows_all_controls_and_tabs(app):
    assert [w.label for w in app.sidebar.multiselect] == ["Location", "Sector", "Organisation type"]
    assert any(b.key == "reset_filters" for b in app.sidebar.button)
    assert [t.label for t in app.tabs] == [
        "Overview",
        "Company and target explorer",
        "Data quality and methodology",
    ]
    assert [m.label for m in app.metric] == [
        "Registered companies",
        "Validated near-term",
        "Validated net-zero",
        "Geographic locations",
    ]
    assert any("Corporate Climate Targets Explorer" in h.value for h in app.header)
    assert any("voluntary" in c.lower() for c in _captions(app))


@pytest.mark.snapshot
def test_default_values_equal_the_independent_recount(app, reference):
    assert _metrics(app) == {
        "Registered companies": fmt_int(reference["distinct_company_ids"]),
        "Validated near-term": fmt_pct(
            100 * reference["near_term_status"]["Validated Targets"] / reference["company_rows"]
        ),
        "Validated net-zero": fmt_pct(
            100 * reference["net_zero_status"]["Validated Targets"] / reference["company_rows"]
        ),
        "Geographic locations": str(reference["distinct_locations"]),
    }
    assert _metrics(app)["Validated near-term"] == "77.1%"
    assert _metrics(app)["Validated net-zero"] == "18.1%"


@pytest.mark.snapshot
@pytest.mark.parametrize("location", ["Japan", UK])
def test_location_filter_changes_the_cards(app, reference, location):
    _select(app, "Location").set_value([location]).run()
    assert not app.exception
    ref = reference["by_location"][location]
    metrics = _metrics(app)
    assert metrics["Registered companies"] == fmt_int(ref["companies"])
    assert metrics["Validated near-term"] == fmt_pct(
        100 * ref["near_term_validated"] / ref["companies"]
    )
    assert metrics["Validated net-zero"] == fmt_pct(
        100 * ref["net_zero_validated"] / ref["companies"]
    )
    assert metrics["Geographic locations"] == "1"
    assert (
        f"{fmt_int(ref['near_term_validated'])} of {fmt_int(ref['companies'])} "
        "registered companies" in _captions(app)
    )


@pytest.mark.snapshot
def test_sector_and_organisation_filters_intersect(app, processed):
    _select(app, "Sector").set_value(["Professional Services"]).run()
    _select(app, "Organisation type").set_value(["SME"]).run()
    companies = processed["companies"]
    expected = len(
        companies[
            (companies["sector"] == "Professional Services")
            & (companies["organization_type"] == "SME")
        ]
    )
    assert _metrics(app)["Registered companies"] == fmt_int(expected)


def test_filters_drive_the_explorer_table_and_cards_from_one_population(app, processed):
    _select(app, "Location").set_value(["Japan"]).run()
    shown = next(
        d.value
        for d in app.dataframe
        if "sbti_id" in d.value.columns
        and "company_name" in d.value.columns
        and "row_entry_id" not in d.value.columns
    )
    expected = analysis.company_display_table(
        analysis.filter_companies(processed["companies"], ["Japan"])
    )
    assert shown.equals(expected)
    assert _metrics(app)["Registered companies"] == fmt_int(len(shown))


def test_no_match_combination_shows_empty_state_and_no_cards(app, processed):
    companies = processed["companies"]
    in_japan = set(companies.loc[companies["location"] == "Japan", "sector"])
    absent = sorted(set(companies["sector"]) - in_japan)[0]
    _select(app, "Location").set_value(["Japan"]).run()
    _select(app, "Sector").set_value([absent]).run()
    assert not app.exception
    assert any(i.value == "No records match the selected filters" for i in app.info)
    assert len(app.metric) == 0


def test_reset_filters_restores_defaults(app):
    _select(app, "Location").set_value(["Japan"]).run()
    assert _metrics(app)["Geographic locations"] == "1"
    next(b for b in app.sidebar.button if b.key == "reset_filters").click().run()
    assert not app.exception
    assert _select(app, "Location").value == []
    assert _metrics(app)["Geographic locations"] == "113"


def test_company_search_shows_linked_records(app, processed):
    app.text_input(key="company_query").set_value("HOKKAN HOLDINGS").run()
    assert not app.exception
    box = app.selectbox(key="company_choice")
    assert len(box.options) == 1
    sbti_id = box.value
    expected = processed["targets"][processed["targets"]["sbti_id"] == sbti_id]
    shown = next(
        d.value
        for d in app.dataframe
        if "row_entry_id" in d.value.columns and len(d.value) == len(expected)
    )
    assert set(shown["row_entry_id"]) == set(expected["row_entry_id"])
    assert (shown["sbti_id"] == sbti_id).all()


def test_search_with_no_result_is_reported(app):
    app.text_input(key="company_query").set_value("zzzz-no-such-company-zzzz").run()
    assert any("No company in the current selection" in i.value for i in app.info)


def test_minimum_group_size_changes_the_paired_chart_caption(app):
    app.sidebar.number_input[0].set_value(500).run()
    assert not app.exception
    assert any("Locations with at least 500 registered companies" in c for c in _captions(app))


def test_paired_chart_note_appears_when_no_location_is_large_enough(app, processed):
    counts = processed["companies"]["location"].value_counts()
    small = counts[counts < 30].index[0]
    _select(app, "Location").set_value([small]).run()
    assert not app.exception
    assert any("No location in this selection has at least 30" in i.value for i in app.info)
    assert len(app.metric) == 4  # cards still render for a small but non-empty selection


def test_quality_tab_reads_real_reports(app, processed):
    import json

    manifest = json.loads((config.REPORTS_DIR / "source_manifest.json").read_text())
    tables = [d.value for d in app.dataframe]
    sources = next(t for t in tables if "SHA-256" in t.columns)
    assert set(sources["SHA-256"]) == {f["sha256"] for f in manifest["files"].values()}
    raw_vs_processed = next(t for t in tables if "Raw rows" in t.columns)
    assert raw_vs_processed["Processed rows"].tolist() == [
        len(processed["companies"]),
        len(processed["targets"]),
    ]
    checks = next(
        t for t in tables if "Expected" in t.columns and "Check" in t.columns and len(t) > 6
    )
    assert set(checks["Result"]) == {"Pass"}
    junit = config.REPORTS_DIR / "pytest_junit.xml"
    assert any(s.value == "Automated test run" for s in app.subheader) == junit.exists()


def test_processed_files_are_the_only_data_source_and_error_is_clear(tmp_path):
    import pytest as _pytest

    with _pytest.raises(datasets.DataNotBuiltError, match="python scripts/build_data.py"):
        datasets.load_companies(tmp_path / "missing.csv")


def _details_text(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown if "ct-detail-value" in m.value)


@pytest.mark.snapshot
def test_data_details_panel_shows_years_and_counts_and_ignores_filters(app, reference):
    first = min(reference["company_min_date_updated"], reference["target_min_date_published"])
    last = max(reference["company_max_date_updated"], reference["target_max_date_published"])
    expected = [
        f"{first[:4]} to {last[:4]}",
        str(reference["distinct_locations"]),
        str(reference["distinct_sectors"]),
        str(reference["distinct_regions"]),
    ]
    text = _details_text(app)
    for value in expected:
        assert value in text
    _select(app, "Location").set_value(["Japan"]).run()
    assert not app.exception
    assert all(value in _details_text(app) for value in expected)  # unchanged by the filter
