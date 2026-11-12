"""Filters, multi-filter intersections, record selection and CSV exports."""

from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest

from climate_targets import analysis, datasets

UK = "United Kingdom of Great Britain and Northern Ireland"


def _expected(reference, group, name):
    g = reference[group][name]
    return g["companies"], g["near_term_validated"], g["net_zero_validated"]


def _kpi_tuple(filtered):
    k = analysis.get_kpis(filtered)
    return k["companies"], k["near_term_validated"], k["net_zero_validated"]


@pytest.mark.parametrize("location", ["Japan", UK, "United States of America"])
def test_single_location_filter_matches_independent_recount(location, companies, reference):
    filtered = analysis.filter_companies(companies, locations=[location])
    assert _kpi_tuple(filtered) == _expected(reference, "by_location", location)
    assert filtered["sbti_id"].is_unique
    assert analysis.get_kpis(filtered)["locations"] == 1


def test_japan_and_united_kingdom_company_counts(companies):
    assert len(analysis.filter_companies(companies, locations=["Japan"])) == 2685
    assert len(analysis.filter_companies(companies, locations=[UK])) == 1980


def test_sector_filter_drives_every_view_from_one_population(companies, targets, reference):
    sector = "Professional Services"
    filtered = analysis.filter_companies(companies, sectors=[sector])
    assert _kpi_tuple(filtered) == _expected(reference, "by_sector", sector)
    ids = set(filtered["sbti_id"])
    n = len(filtered)

    by_sector = analysis.status_by_sector(filtered)
    assert by_sector["sector"].tolist() == [sector] and by_sector["n"].tolist() == [n]
    assert analysis.location_counts(filtered, None)["companies"].sum() == n
    assert analysis.location_target_comparison(filtered, 1)["n"].sum() == n
    assert analysis.status_counts(filtered, "net_zero_status")["companies"].sum() == n

    records = analysis.filter_targets(targets, filtered)
    assert set(records["sbti_id"]) == ids  # every company has at least one record
    per_company = Counter(records["sbti_id"])
    assert sum(per_company.values()) == len(records)
    assert len(analysis.company_display_table(filtered)) == n
    # one-to-many: more target records than companies, but company counts are unchanged
    assert len(records) > n
    assert analysis.get_kpis(filtered)["companies"] == n


def test_organization_type_filter(companies, reference):
    filtered = analysis.filter_companies(companies, organization_types=["SME"])
    assert _kpi_tuple(filtered) == _expected(reference, "by_organization_type", "SME")


def test_multiple_filters_intersect_and_have_no_duplicate_companies(companies, raw_frames):
    raw = raw_frames["companies"]
    expected = int(((raw["location"] == "Japan") & (raw["organization_type"] == "SME")).sum())
    filtered = analysis.filter_companies(companies, locations=["Japan"], organization_types=["SME"])
    assert len(filtered) == expected > 0
    assert filtered["sbti_id"].is_unique
    japan = analysis.filter_companies(companies, locations=["Japan"])
    sme = analysis.filter_companies(companies, organization_types=["SME"])
    assert len(filtered) < min(len(japan), len(sme))
    assert set(filtered["sbti_id"]) == set(japan["sbti_id"]) & set(sme["sbti_id"])


def test_values_within_one_field_combine_as_a_union(companies, reference):
    both = analysis.filter_companies(companies, locations=["Japan", "China"])
    assert (
        len(both)
        == reference["by_location"]["Japan"]["companies"]
        + reference["by_location"]["China"]["companies"]
    )


def test_empty_filter_lists_and_none_mean_no_restriction(companies):
    assert len(analysis.filter_companies(companies)) == len(companies)
    assert len(analysis.filter_companies(companies, [], [], [])) == len(companies)


def test_filter_with_no_match_is_empty_and_safe(companies, targets):
    sectors_in_japan = set(companies.loc[companies["location"] == "Japan", "sector"])
    absent = sorted(set(companies["sector"]) - sectors_in_japan)[0]
    filtered = analysis.filter_companies(companies, locations=["Japan"], sectors=[absent])
    assert filtered.empty
    assert analysis.filter_targets(targets, filtered).empty
    assert analysis.company_display_table(filtered).empty


def test_unrecorded_net_zero_is_labelled_not_recorded_in_the_display_table(companies):
    shown = analysis.company_display_table(companies)
    assert (shown["net_zero_status"] == "Not recorded").sum() == (
        companies["net_zero_status"] == ""
    ).sum()
    assert (shown["net_zero_status"] == "").sum() == 0
    assert (shown["net_zero_status"] == "Commitment Removed").sum() == (
        companies["net_zero_status"] == "Commitment Removed"
    ).sum()


# ---- company search and linked records ----


def test_company_records_are_selected_by_id_and_keep_record_grain(companies, targets, raw_frames):
    raw = raw_frames["targets"]
    counts = Counter(raw["sbti_id"].astype(float).astype(int).astype(str))
    sbti_id, expected = counts.most_common(1)[0]
    records = analysis.get_company_target_records(targets, companies, sbti_id)
    assert len(records) == expected > 1
    assert (records["sbti_id"] == sbti_id).all()
    assert records["row_entry_id"].is_unique
    assert set(records["action"]) <= {"Target", "Commitment"}


def test_company_outside_the_filtered_set_has_no_records(companies, targets):
    japan = analysis.filter_companies(companies, locations=["Japan"])
    outside = companies.loc[companies["location"] != "Japan", "sbti_id"].iloc[0]
    assert analysis.get_company_target_records(targets, japan, outside).empty


def test_search_by_name_and_by_id(companies, targets):
    row = companies[companies["company_name"].str.len() > 12].iloc[100]
    by_name = analysis.search_companies(companies, row["company_name"][3:11].upper())
    assert row["sbti_id"] in set(by_name["sbti_id"])
    by_id = analysis.search_companies(companies, row["sbti_id"])
    assert by_id["sbti_id"].tolist() == [row["sbti_id"]]
    assert analysis.search_companies(companies, "   ").empty
    assert analysis.search_companies(companies, "zzzz-no-such-company-zzzz").empty
    assert not analysis.get_company_target_records(targets, companies, row["sbti_id"]).empty


def test_search_respects_the_current_filters(companies):
    japan = analysis.filter_companies(companies, locations=["Japan"])
    other = companies.loc[companies["location"] != "Japan", "company_name"].iloc[0]
    assert (
        analysis.search_companies(japan, other).empty
        or (analysis.search_companies(japan, other)["location"] == "Japan").all()
    )


def test_hokkan_holdings_links_to_its_records(companies, targets):
    found = analysis.search_companies(companies, "HOKKAN HOLDINGS")
    assert len(found) == 1
    records = analysis.get_company_target_records(targets, companies, found.iloc[0]["sbti_id"])
    assert len(records) >= 5
    assert records["company_name"].eq("HOKKAN HOLDINGS LIMITED").all()


# ---- exports ----


def _roundtrip(frame: pd.DataFrame) -> pd.DataFrame:
    import io

    return pd.read_csv(
        io.BytesIO(datasets.to_csv_bytes(frame)),
        dtype=str,
        keep_default_na=False,
        na_values=[],
        encoding="utf-8-sig",
    )


def test_company_export_is_exactly_the_displayed_frame(companies):
    filtered = analysis.filter_companies(companies, locations=["Japan"], organization_types=["SME"])
    shown = analysis.company_display_table(filtered)
    back = _roundtrip(shown)
    pd.testing.assert_frame_equal(shown, back)
    assert len(back) == len(filtered)  # no silent truncation


def test_target_export_is_exactly_the_displayed_frame(companies, targets):
    filtered = analysis.filter_companies(companies, locations=[UK])
    records = analysis.filter_targets(targets, filtered)
    shown = analysis.target_display_table(records)
    back = _roundtrip(shown)
    pd.testing.assert_frame_equal(shown, back)
    assert len(back) == len(records) > len(filtered)
    assert set(back["sbti_id"]) == set(filtered["sbti_id"])


def test_full_export_has_every_row(companies, targets):
    assert len(_roundtrip(analysis.company_display_table(companies))) == len(companies)
    assert len(_roundtrip(analysis.target_display_table(targets))) == len(targets)


def test_export_keeps_degree_sign_and_na_literal(targets):
    shown = analysis.target_display_table(targets)
    text = datasets.to_csv_bytes(shown).decode("utf-8-sig")
    assert "1.5°C" in text
    back = _roundtrip(shown)
    assert (back["commitment_type"] == "NA").sum() == (shown["commitment_type"] == "NA").sum() > 0
