"""Key integrity and the one-to-many company/target relationship."""

from __future__ import annotations

from climate_targets import validate


def test_company_ids_unique_and_valid(companies):
    assert companies["sbti_id"].is_unique
    assert companies["sbti_id"].str.fullmatch(r"4\d{7}").all()


def test_target_row_ids_unique(targets):
    assert targets["row_entry_id"].is_unique


def test_no_orphans_and_no_companies_without_targets(companies, targets):
    assert (~targets["sbti_id"].isin(set(companies["sbti_id"]))).sum() == 0
    assert (~companies["sbti_id"].isin(set(targets["sbti_id"]))).sum() == 0


def test_row_entry_id_suffix_matches_company_id(targets):
    assert (targets["row_entry_id"].str.rsplit("-", n=1).str[-1] == targets["sbti_id"]).all()


def test_counts_equal_independent_recount(companies, targets, reference):
    assert companies["sbti_id"].nunique() == reference["distinct_company_ids"]
    assert targets["row_entry_id"].nunique() == reference["distinct_row_entry_ids"]
    assert len(targets) == reference["target_rows"]
    assert reference["orphan_target_records"] == 0
    assert reference["companies_without_targets"] == 0


def test_sector_location_region_agree_across_tables(companies, targets):
    merged = targets.merge(companies, on="sbti_id", suffixes=("_t", "_c"))
    for column in ("sector", "location", "region", "organization_type"):
        assert (merged[f"{column}_t"] == merged[f"{column}_c"]).all(), column


def test_company_name_whitespace_discrepancy_does_not_break_the_join(
    raw_frames, companies, targets
):
    """The source has one company whose target-table name carries a full-width trailing space."""
    raw_c, raw_t = raw_frames["companies"], raw_frames["targets"]
    merged = raw_t.merge(raw_c[["sbti_id", "company_name"]], on="sbti_id", suffixes=("_t", "_c"))
    different = merged[merged["company_name_t"] != merged["company_name_c"]]
    assert different["sbti_id"].nunique() == 1  # a single company
    assert len(merged) == len(raw_t)  # join by ID still matches every target row
    # after cleaning the names agree and the join is unchanged
    after = targets.merge(
        companies[["sbti_id", "company_name"]], on="sbti_id", suffixes=("_t", "_c")
    )
    assert (after["company_name_t"] == after["company_name_c"]).all()
    assert len(after) == len(targets)


def test_join_is_one_to_many_and_never_inflates_company_counts(companies, targets):
    joined = targets.merge(companies, on="sbti_id", how="left", validate="many_to_one")
    assert len(joined) == len(targets)  # target grain preserved
    assert joined["sbti_id"].nunique() == len(companies)  # unique companies, not rows
    assert len(joined) > len(companies)  # a naive row count would overstate companies
    per_company = targets.groupby("sbti_id").size()
    assert per_company.min() >= 1
    assert per_company.sum() == len(targets)


def test_all_validation_checks_pass(companies, targets):
    results = validate.run_all_checks(companies, targets)
    assert results
    failed = [r for r in results if not r.passed]
    assert not failed, failed


def test_orphan_check_detects_a_removed_company(companies, targets):
    """Negative case built from real rows: drop the first company from the company table."""
    dropped = companies.iloc[0]["sbti_id"]
    expected = int((targets["sbti_id"] == dropped).sum())
    result = validate.check_orphans(companies.iloc[1:], targets)
    assert not result.passed
    assert result.count == expected > 0


def test_companies_without_targets_check_detects_a_removed_target_group(companies, targets):
    dropped = companies.iloc[0]["sbti_id"]
    result = validate.check_companies_without_targets(
        companies, targets[targets["sbti_id"] != dropped]
    )
    assert result.count == 1 and not result.passed


def test_duplicate_check_detects_a_repeated_company(companies):
    doubled = companies.iloc[[0, 0, 1]]
    results = {r.name: r for r in validate.check_company_ids(doubled)}
    assert results["company_ids_unique"].count == 1
