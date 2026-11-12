"""Every reported number is recomputed from the source by an independent route."""

from __future__ import annotations

import pandas as pd
import pytest

from climate_targets import analysis, config
from climate_targets.formatting import display_status, fmt_int, fmt_pct, pct

UK = "United Kingdom of Great Britain and Northern Ireland"


# ---- formatting rules (no data needed) ----


def test_fmt_pct_rounds_half_up_from_the_unrounded_value():
    assert fmt_pct(2.25) == "2.3%"
    assert fmt_pct(0.05) == "0.1%"
    assert fmt_pct(0.0) == "0.0%"
    assert fmt_pct(100.0) == "100.0%"
    assert fmt_pct(77.11296284693941) == "77.1%"
    assert fmt_pct(None) == "n/a"
    assert fmt_int(15961) == "15,961"


def test_pct_never_divides_by_zero():
    assert pct(5, 0) is None
    assert pct(0, 0) is None
    assert pct(1, 4) == 25.0


def test_blank_status_is_shown_as_not_recorded():
    assert display_status("") == config.NOT_RECORDED
    assert display_status("Validated Targets") == "Validated Targets"


# ---- headline figures against the independent recount ----


@pytest.mark.snapshot
def test_full_data_kpis(companies, reference):
    k = analysis.get_kpis(companies)
    assert k["companies"] == reference["distinct_company_ids"]
    assert k["near_term_validated"] == reference["near_term_status"]["Validated Targets"]
    assert k["net_zero_validated"] == reference["net_zero_status"]["Validated Targets"]
    assert k["locations"] == reference["distinct_locations"]
    assert k["sectors"] == reference["distinct_sectors"]
    assert fmt_pct(k["near_term_share"]) == "77.1%"
    assert fmt_pct(k["net_zero_share"]) == "18.1%"


@pytest.mark.snapshot
def test_status_counts_equal_reference_and_keep_not_recorded_separate(companies, reference):
    near = analysis.status_counts(companies, "near_term_status").set_index("status")["companies"]
    assert near.to_dict() == reference["near_term_status"]
    net = analysis.status_counts(companies, "net_zero_status").set_index("status")["companies"]
    expected = dict(reference["net_zero_status"])
    expected[config.NOT_RECORDED] = expected.pop("(blank)")
    assert net.to_dict() == expected
    assert net[config.NOT_RECORDED] == reference["company_net_zero_blank"]
    assert net[config.REMOVED] == reference["net_zero_status"]["Commitment Removed"]  # not inflated
    assert net.sum() == len(companies)


@pytest.mark.snapshot
def test_action_counts_and_target_table_status_is_not_used_for_company_kpis(
    companies, targets, reference
):
    summary = analysis.summarize_target_records(targets)
    assert summary["action"] == reference["target_action"]
    assert (targets["status"] == "Other").sum() == reference["target_status_other_rows"]
    target_validated = int((targets["status"] == "Validated Targets").sum())
    kpis = analysis.get_kpis(companies)
    assert kpis["near_term_validated"] != target_validated
    only_company_columns = companies[
        ["sbti_id", "location", "sector", "near_term_status", "net_zero_status"]
    ]
    assert analysis.get_kpis(only_company_columns) == kpis


@pytest.mark.snapshot
def test_every_location_matches_the_independent_recount(companies, reference):
    table = analysis.location_target_comparison(companies, min_n=1).set_index("location")
    assert len(table) == reference["distinct_locations"]
    for name, expected in reference["by_location"].items():
        row = table.loc[name]
        assert (row["n"], row["near_term_validated"], row["net_zero_validated"]) == (
            expected["companies"],
            expected["near_term_validated"],
            expected["net_zero_validated"],
        ), name


@pytest.mark.snapshot
def test_every_sector_matches_the_independent_recount_and_sums_to_total(companies, reference):
    table = analysis.status_by_sector(companies, top_n=None).set_index("sector")
    assert len(table) == reference["distinct_sectors"]
    assert table["n"].sum() == len(companies)
    assert table["reconciles"].all()
    for name, expected in reference["by_sector"].items():
        row = table.loc[name]
        assert (row["n"], row["validated"], row["net_zero_validated"]) == (
            expected["companies"],
            expected["near_term_validated"],
            expected["net_zero_validated"],
        ), name


@pytest.mark.snapshot
def test_location_counts_sum_and_rank(companies, reference):
    table = analysis.location_counts(companies, top_n=None)
    assert table["companies"].sum() == len(companies)
    top = table.head(3)
    assert top["location"].tolist()[0] == "Japan"
    assert top["companies"].tolist() == sorted(top["companies"], reverse=True)
    expected_top = sorted(
        reference["by_location"].items(), key=lambda kv: (-kv[1]["companies"], kv[0])
    )[:10]
    assert analysis.location_counts(companies, 10)["location"].tolist() == [
        k for k, _ in expected_top
    ]


@pytest.mark.snapshot
def test_brief_sanity_examples(companies):
    table = analysis.location_target_comparison(companies, min_n=1).set_index("location")
    japan, uk = table.loc["Japan"], table.loc[UK]
    assert (fmt_pct(japan["near_term_pct"]), fmt_pct(japan["net_zero_pct"])) == ("96.9%", "4.2%")
    assert (fmt_pct(uk["near_term_pct"]), fmt_pct(uk["net_zero_pct"])) == ("80.1%", "35.2%")
    assert uk["n"] == 1980


def test_all_rates_lie_between_zero_and_one_hundred(companies):
    tables = [
        analysis.status_by_sector(companies, None),
        analysis.location_target_comparison(companies, 1),
        analysis.location_counts(companies, None),
        analysis.status_counts(companies, "net_zero_status"),
    ]
    for table in tables:
        for column in [c for c in table.columns if c.endswith("_pct")]:
            assert table[column].between(0, 100).all(), column


def test_status_shares_in_each_group_sum_to_100(companies):
    table = analysis.status_by_sector(companies, None)
    total = table[["validated_pct", "commitment_pct", "removed_pct"]].sum(axis=1)
    assert (total - 100).abs().max() < 1e-9


# ---- empty selection ----


@pytest.fixture(scope="module")
def empty_selection(companies):
    """A real filter combination with no matching companies: a sector with no company in Japan."""
    japan_sectors = set(companies.loc[companies["location"] == "Japan", "sector"])
    absent = sorted(set(companies["sector"]) - japan_sectors)
    assert absent, "every sector has a Japan company; choose another location"
    return analysis.filter_companies(companies, locations=["Japan"], sectors=[absent[0]])


def test_empty_selection_gives_empty_results_without_errors(empty_selection):
    assert len(empty_selection) == 0
    kpis = analysis.get_kpis(empty_selection)
    assert kpis["companies"] == 0
    assert kpis["near_term_share"] is None and kpis["net_zero_share"] is None
    assert analysis.status_by_sector(empty_selection).empty
    assert analysis.location_counts(empty_selection).empty
    assert analysis.location_target_comparison(empty_selection).empty
    assert analysis.status_counts(empty_selection, "net_zero_status").empty
    assert analysis.build_insights(empty_selection) == []


# ---- determinism ----


def test_results_do_not_depend_on_row_order(companies):
    shuffled = companies.sample(frac=1.0, random_state=7).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        analysis.status_by_sector(companies, 25), analysis.status_by_sector(shuffled, 25)
    )
    pd.testing.assert_frame_equal(
        analysis.location_counts(companies, 25), analysis.location_counts(shuffled, 25)
    )
    pd.testing.assert_frame_equal(
        analysis.location_target_comparison(companies, 30),
        analysis.location_target_comparison(shuffled, 30),
    )
    assert analysis.build_insights(companies) == analysis.build_insights(shuffled)


def test_ties_are_broken_alphabetically(companies):
    table = analysis.location_counts(companies, None)
    ties = table[table.duplicated("companies", keep=False)]
    assert not ties.empty
    for _, group in ties.groupby("companies"):
        assert group["location"].tolist() == sorted(group["location"])


# ---- insights ----


@pytest.mark.snapshot
def test_insights_use_the_same_numbers_as_the_independent_recount(companies, reference):
    statements = analysis.build_insights(companies, min_n=30)
    assert len(statements) == 2
    qualifying = {k: v for k, v in reference["by_location"].items() if v["companies"] >= 30}
    share = {k: v["near_term_validated"] / v["companies"] for k, v in qualifying.items()}
    best = max(share, key=lambda k: (share[k], -len(k)))
    worst = min(share, key=lambda k: (share[k], len(k)))
    assert f"Among the {len(qualifying)} locations" in statements[0]
    assert f"highest in {best}" in statements[0]
    assert f"lowest in {worst}" in statements[0]
    assert "registered companies" in statements[0]


def test_insights_are_suppressed_for_a_group_below_the_minimum(companies):
    counts = companies["location"].value_counts()
    small = counts[counts < 30].index[0]
    assert analysis.build_insights(analysis.filter_companies(companies, locations=[small])) == []


def test_insights_change_with_filters(companies):
    full = analysis.build_insights(companies)
    japan = analysis.build_insights(analysis.filter_companies(companies, locations=["Japan"]))
    assert full and japan and full != japan
    assert "sectors" in japan[0]


# ---- target-record summaries ----


@pytest.mark.snapshot
def test_target_only_summaries_exclude_commitments_and_report_exclusions(targets, raw_frames):
    raw = raw_frames["targets"]
    target_rows = raw[raw["action"] == "Target"]
    assert len(target_rows) == 29513
    years, excluded = analysis.target_year_counts(targets)
    expected_missing = int(target_rows["target_year"].isin(["", "NA"]).sum())
    assert excluded == expected_missing
    assert years["records"].sum() + excluded == len(target_rows)
    scopes, no_scope = analysis.scope_counts(targets)
    assert scopes["records"].sum() + no_scope == len(target_rows)
    assert not scopes["scope"].str.contains(r"\.").any()
    types, no_type = analysis.target_type_counts(targets)
    assert types["records"].sum() + no_type == len(target_rows)
    assert years["target_year"].between(2000, 2100).all()


def test_eda_summary_is_computed_and_consistent(companies, targets, reference):
    summary = analysis.get_eda_summary(companies, targets, {"note": "test"})
    assert summary["rows"] == {
        "companies": reference["company_rows"],
        "targets": reference["target_rows"],
    }
    assert summary["distinct"]["locations"] == reference["distinct_locations"]
    assert (
        summary["net_zero_status"][config.NOT_RECORDED]["companies"]
        == reference["company_net_zero_blank"]
    )
    assert summary["records_per_company"]["min"] >= 1
    assert summary["date_updated"]["max"] == reference["company_max_date_updated"]


@pytest.mark.snapshot
def test_data_details_match_the_independent_recount(companies, targets, reference):
    details = analysis.get_data_details(companies, targets)
    first = min(reference["company_min_date_updated"], reference["target_min_date_published"])
    last = max(reference["company_max_date_updated"], reference["target_max_date_published"])
    assert details == {
        "first_year": int(first[:4]),
        "last_year": int(last[:4]),
        "locations": reference["distinct_locations"],
        "sectors": reference["distinct_sectors"],
        "regions": reference["distinct_regions"],
    }
