"""Integrity checks on the cleaned tables and the one-to-many company/target relationship."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import pandas as pd

from . import config


@dataclass
class CheckResult:
    """Outcome of one check. ``count`` is the number of offending rows or the value measured."""

    name: str
    description: str
    count: int
    expected: int
    passed: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _result(name: str, description: str, count: int, expected: int = 0) -> CheckResult:
    return CheckResult(name, description, int(count), int(expected), int(count) == int(expected))


def check_company_ids(companies: pd.DataFrame) -> list[CheckResult]:
    pattern = re.compile(config.SBTI_ID_PATTERN)
    invalid = ~companies["sbti_id"].map(lambda v: bool(pattern.match(v)))
    return [
        _result("company_ids_unique", "Duplicated company sbti_id values",
                companies["sbti_id"].duplicated().sum()),
        _result("company_ids_valid", "Company sbti_id values that are not 4 followed by 7 digits",
                invalid.sum()),
    ]  # fmt: skip


def check_target_ids(targets: pd.DataFrame) -> list[CheckResult]:
    pattern = re.compile(config.SBTI_ID_PATTERN)
    invalid = ~targets["sbti_id"].map(lambda v: bool(pattern.match(v)))
    return [
        _result("target_row_ids_unique", "Duplicated target row_entry_id values",
                targets["row_entry_id"].duplicated().sum()),
        _result("target_company_ids_valid",
                "Target sbti_id values that are not 4 followed by 7 digits", invalid.sum()),
    ]  # fmt: skip


def check_orphans(companies: pd.DataFrame, targets: pd.DataFrame) -> CheckResult:
    known = set(companies["sbti_id"])
    return _result(
        "orphan_target_records",
        "Target records whose sbti_id is not in the company table",
        (~targets["sbti_id"].isin(known)).sum(),
    )


def check_companies_without_targets(companies: pd.DataFrame, targets: pd.DataFrame) -> CheckResult:
    linked = set(targets["sbti_id"])
    return _result(
        "companies_without_targets",
        "Companies with no target or commitment record",
        (~companies["sbti_id"].isin(linked)).sum(),
    )


def check_suffix_match(targets: pd.DataFrame) -> CheckResult:
    suffix = targets["row_entry_id"].str.rsplit("-", n=1).str[-1]
    return _result(
        "row_entry_id_suffix_matches_sbti_id",
        "Target records whose row_entry_id suffix differs from sbti_id",
        (suffix != targets["sbti_id"]).sum(),
    )


def check_attribute_agreement(companies: pd.DataFrame, targets: pd.DataFrame) -> list[CheckResult]:
    """Sector, location and region must agree between a target record and its company."""
    merged = targets[["sbti_id", "sector", "location", "region"]].merge(
        companies[["sbti_id", "sector", "location", "region"]],
        on="sbti_id", how="left", suffixes=("_t", "_c"),
    )  # fmt: skip
    return [
        _result(
            f"{col}_agrees_across_tables",
            f"Target records whose {col} differs from the linked company",
            (merged[f"{col}_t"] != merged[f"{col}_c"]).sum(),
        )
        for col in ("sector", "location", "region")
    ]


def reconcile_status_counts(companies: pd.DataFrame) -> list[CheckResult]:
    counts = companies["near_term_status"].value_counts()
    unknown = companies.loc[
        ~companies["near_term_status"].isin(config.NEAR_TERM_STATUSES), "near_term_status"
    ]
    return [
        _result("near_term_statuses_sum_to_companies",
                "Companies not covered by the three near-term statuses",
                len(companies) - int(counts.reindex(config.NEAR_TERM_STATUSES).fillna(0).sum())),
        _result("near_term_status_values_known",
                "Companies with an unrecognised near-term status", len(unknown)),
    ]  # fmt: skip


def run_all_checks(companies: pd.DataFrame, targets: pd.DataFrame) -> list[CheckResult]:
    results: list[CheckResult] = []
    results += check_company_ids(companies)
    results += check_target_ids(targets)
    results.append(check_orphans(companies, targets))
    results.append(check_companies_without_targets(companies, targets))
    results.append(check_suffix_match(targets))
    results += check_attribute_agreement(companies, targets)
    results += reconcile_status_counts(companies)
    return results


def missingness(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-column share of blank cells and of the literal ``NA``, as percentages of rows."""
    n = len(frame)
    rows = []
    for column in frame.columns:
        if column.endswith("_raw"):
            continue
        blank = int((frame[column] == "").sum())
        na = int((frame[column] == "NA").sum())
        rows.append(
            {
                "column": column,
                "blank": blank,
                "blank_pct": round(100 * blank / n, 2),
                "na_literal": na,
                "na_literal_pct": round(100 * na / n, 2),
                "distinct": int(frame[column].nunique()),
            }
        )
    return pd.DataFrame(rows)
