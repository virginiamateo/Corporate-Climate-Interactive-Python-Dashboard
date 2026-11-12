"""Pure filtering and aggregation functions.

Grain and denominators:

* Company KPIs and group shares are computed on the company table (one row per ``sbti_id``).
  The denominator is always the number of registered companies in the filtered group.
* Target records are selected by the IDs of the filtered companies and keep their own grain.
  They never feed a company count.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

from . import clean, config
from .formatting import display_status, fmt_int, fmt_pct, pct

STATUS_COLUMNS = {"validated": config.VALIDATED, "commitment": config.COMMITMENT,
                  "removed": config.REMOVED}  # fmt: skip


def _restrict(frame: pd.DataFrame, column: str, values: Iterable[str] | None) -> pd.DataFrame:
    chosen = list(values) if values is not None else []
    return frame if not chosen else frame[frame[column].isin(chosen)]


def filter_companies(
    companies: pd.DataFrame,
    locations: Sequence[str] | None = None,
    sectors: Sequence[str] | None = None,
    organization_types: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Companies matching every non-empty filter (intersection). One row per company.

    An empty list or ``None`` means no restriction on that field.
    """
    out = _restrict(companies, "location", locations)
    out = _restrict(out, "sector", sectors)
    out = _restrict(out, "organization_type", organization_types)
    return out.drop_duplicates("sbti_id").reset_index(drop=True)


def filter_targets(targets: pd.DataFrame, filtered_companies: pd.DataFrame) -> pd.DataFrame:
    """Target and commitment records of the filtered companies, selected by ID."""
    return targets[targets["sbti_id"].isin(set(filtered_companies["sbti_id"]))].reset_index(
        drop=True
    )


def get_kpis(filtered: pd.DataFrame) -> dict:
    """Headline numbers for the filtered companies. Shares are ``None`` if there are none."""
    n = int(filtered["sbti_id"].nunique())
    near = int((filtered["near_term_status"] == config.VALIDATED).sum())
    net = int((filtered["net_zero_status"] == config.VALIDATED).sum())
    return {
        "companies": n,
        "near_term_validated": near,
        "near_term_share": pct(near, n),
        "net_zero_validated": net,
        "net_zero_share": pct(net, n),
        "locations": int(filtered["location"].nunique()),
        "sectors": int(filtered["sector"].nunique()),
    }


def _sorted(table: pd.DataFrame, count_column: str, key: str) -> pd.DataFrame:
    return table.sort_values([count_column, key], ascending=[False, True], kind="mergesort")


def _group_status(filtered: pd.DataFrame, key: str) -> pd.DataFrame:
    """Per group: n, near-term status counts and shares, net-zero validated count and share."""
    if filtered.empty:
        return pd.DataFrame(
            columns=[key, "n", "validated", "commitment", "removed", "validated_pct",
                     "commitment_pct", "removed_pct", "reconciles", "net_zero_validated",
                     "net_zero_pct"]
        )  # fmt: skip
    g = filtered.groupby(key, sort=False)
    out = pd.DataFrame({"n": g["sbti_id"].nunique()})
    for name, status in STATUS_COLUMNS.items():
        out[name] = g["near_term_status"].apply(lambda s, status=status: int((s == status).sum()))
    out["net_zero_validated"] = g["net_zero_status"].apply(
        lambda s: int((s == config.VALIDATED).sum())
    )
    for name in STATUS_COLUMNS:
        out[f"{name}_pct"] = 100.0 * out[name] / out["n"]
    out["net_zero_pct"] = 100.0 * out["net_zero_validated"] / out["n"]
    out["reconciles"] = (out["validated"] + out["commitment"] + out["removed"]) == out["n"]
    out = out.reset_index()
    return _sorted(out, "n", key).reset_index(drop=True)


def status_by_sector(
    filtered: pd.DataFrame, top_n: int | None = config.TOP_N_DEFAULT
) -> pd.DataFrame:
    """Near-term status counts and shares for the largest sectors (by registered companies).

    Ties in company count are broken alphabetically by sector.
    """
    table = _group_status(filtered, "sector")
    return table if top_n is None else table.head(top_n).reset_index(drop=True)


def location_counts(
    filtered: pd.DataFrame, top_n: int | None = config.TOP_N_DEFAULT
) -> pd.DataFrame:
    """Unique registered companies by location, largest first. Directory size, not a rate."""
    if filtered.empty:
        return pd.DataFrame(columns=["location", "companies", "share_of_selection_pct"])
    counts = filtered.groupby("location")["sbti_id"].nunique().rename("companies").reset_index()
    counts["share_of_selection_pct"] = 100.0 * counts["companies"] / filtered["sbti_id"].nunique()
    counts = _sorted(counts, "companies", "location").reset_index(drop=True)
    return counts if top_n is None else counts.head(top_n).reset_index(drop=True)


def location_target_comparison(
    filtered: pd.DataFrame, min_n: int = config.DEFAULT_MIN_N, top_n: int | None = None
) -> pd.DataFrame:
    """Validated near-term and net-zero share per location, with the cohort size flag.

    Both shares use the registered companies in that location (within the current filters)
    as the denominator. ``meets_min_n`` is False for groups smaller than ``min_n``.
    """
    table = _group_status(filtered, "location")
    if table.empty:
        columns = ["location", "n", "near_term_validated", "near_term_pct", "net_zero_validated",
                   "net_zero_pct", "meets_min_n"]  # fmt: skip
        return pd.DataFrame(columns=columns)
    out = table[["location", "n", "validated", "validated_pct", "net_zero_validated",
                 "net_zero_pct"]].rename(
        columns={"validated": "near_term_validated", "validated_pct": "near_term_pct"}
    )  # fmt: skip
    out["meets_min_n"] = out["n"] >= min_n
    return out if top_n is None else out.head(top_n).reset_index(drop=True)


def status_counts(filtered: pd.DataFrame, column: str) -> pd.DataFrame:
    """Companies per status for ``near_term_status`` or ``net_zero_status``.

    A blank status is reported as ``Not recorded``. Zero counts for the known statuses are
    true zeros (the denominator is positive); with no companies the table is empty.
    """
    labels = [*config.NEAR_TERM_STATUSES, config.NOT_RECORDED]
    if filtered.empty:
        return pd.DataFrame(columns=["status", "companies", "share_pct"])
    shown = filtered[column].map(display_status)
    counts = shown.value_counts().reindex(labels).fillna(0).astype(int)
    if column == "near_term_status":
        counts = counts.drop(config.NOT_RECORDED)
    out = counts.rename("companies").rename_axis("status").reset_index()
    out["share_pct"] = 100.0 * out["companies"] / len(filtered)
    return out


def search_companies(filtered: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    """Companies whose name contains ``query`` (case-insensitive) or whose ID starts with it."""
    q = query.strip()
    if not q:
        return filtered.head(0)
    by_name = filtered["company_name"].str.contains(q, case=False, regex=False)
    by_id = filtered["sbti_id"].str.startswith(q)
    return (
        _sorted(filtered[by_name | by_id].assign(_n=0), "_n", "company_name")
        .drop(columns="_n")
        .head(limit)
        .reset_index(drop=True)
    )


def get_company_target_records(
    all_targets: pd.DataFrame, filtered_companies: pd.DataFrame, selected_company_id: str
) -> pd.DataFrame:
    """Target and commitment records of one company, selected by ID.

    Returns no rows if the company is outside the filtered set. Record grain is preserved.
    """
    if selected_company_id not in set(filtered_companies["sbti_id"]):
        return all_targets.head(0)
    return all_targets[all_targets["sbti_id"] == selected_company_id].reset_index(drop=True)


COMPANY_DISPLAY_COLUMNS = [
    "sbti_id", "company_name", "organization_type", "location", "region", "sector",
    "near_term_status", "near_term_target_year", "long_term_status", "net_zero_status",
    "net_zero_year", "date_updated",
]  # fmt: skip
TARGET_DISPLAY_COLUMNS = [
    "row_entry_id", "sbti_id", "company_name", "action", "commitment_type", "commitment_deadline",
    "status", "target", "scope", "type", "sub_type", "target_value", "base_year", "target_year",
    "year_type", "target_classification_short", "validation_route", "date_published",
    "target_wording",
]  # fmt: skip


def company_display_table(filtered: pd.DataFrame) -> pd.DataFrame:
    """Company table as shown and exported in the explorer. Blank status reads ``Not recorded``."""
    out = filtered[COMPANY_DISPLAY_COLUMNS].copy()
    for column in ("near_term_status", "long_term_status", "net_zero_status"):
        out[column] = out[column].map(display_status)
    return out.reset_index(drop=True)


def target_display_table(records: pd.DataFrame) -> pd.DataFrame:
    """Target-record table as shown and exported in the explorer (record grain)."""
    return records[TARGET_DISPLAY_COLUMNS].reset_index(drop=True)


def _target_rows(records: pd.DataFrame) -> pd.DataFrame:
    return records[records["action"] == "Target"]


def _defined(series: pd.Series) -> pd.Series:
    return series[~series.isin(["", "NA"])]


def target_type_counts(records: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Counts of ``type`` for Target records, and the number of Target records without a type."""
    rows = _target_rows(records)
    defined = _defined(rows["type"])
    out = defined.value_counts().rename_axis("type").rename("records").reset_index()
    return _sorted(out, "records", "type").reset_index(drop=True), len(rows) - len(defined)


def scope_counts(records: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Counts of ``scope`` for Target records, and the number of Target records without a scope."""
    rows = _target_rows(records)
    defined = _defined(rows["scope"])
    out = defined.value_counts().rename_axis("scope").rename("records").reset_index()
    return _sorted(out, "records", "scope").reset_index(drop=True), len(rows) - len(defined)


def target_year_counts(records: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Target records by numeric target year, and the number excluded for a missing year.

    Only ``action == 'Target'`` records are considered. Blank and ``NA`` years are excluded,
    not imputed. FY and CY prefixes are removed for the numeric year.
    """
    rows = _target_rows(records)
    defined = _defined(rows["target_year"])
    years = clean.target_year_number(defined).dropna()
    out = years.value_counts().rename_axis("target_year").rename("records").reset_index()
    out = out.sort_values("target_year", kind="mergesort").reset_index(drop=True)
    out["target_year"] = out["target_year"].astype(int)
    return out, len(rows) - len(defined)


def summarize_target_records(records: pd.DataFrame) -> dict:
    """Plain-Python summary of a set of target records, safe to write to JSON."""
    actions = records["action"].value_counts()
    types, no_type = target_type_counts(records)
    scopes, no_scope = scope_counts(records)
    years, no_year = target_year_counts(records)
    return {
        "records": len(records),
        "action": {k: int(v) for k, v in actions.sort_index().items()},
        "target_records": int((records["action"] == "Target").sum()),
        "type": dict(zip(types["type"], types["records"].astype(int), strict=True)),
        "type_not_recorded": no_type,
        "scope": dict(zip(scopes["scope"], scopes["records"].astype(int), strict=True)),
        "scope_not_recorded": no_scope,
        "target_year": {
            int(y): int(c) for y, c in zip(years["target_year"], years["records"], strict=True)
        },
        "target_year_excluded": no_year,
    }


def _extreme(table: pd.DataFrame, column: str, highest: bool) -> pd.Series:
    ordered = table.sort_values([column, "n", "name"], ascending=[not highest, False, True],
                                kind="mergesort")  # fmt: skip
    return ordered.iloc[0]


def build_insights(filtered: pd.DataFrame, min_n: int = config.DEFAULT_MIN_N) -> list[str]:
    """Short descriptive statements for the current selection, with figures and denominators.

    Locations are compared first, then sectors. Groups smaller than ``min_n`` are left out.
    Returns an empty list if no comparison is applicable. The wording is descriptive only.
    """
    if filtered.empty:
        return []
    out: list[str] = []
    for label, key in (("locations", "location"), ("sectors", "sector")):
        table = _group_status(filtered, key)
        table = table[table["n"] >= min_n].rename(columns={key: "name"})
        if len(table) < 2:
            continue
        hi = _extreme(table, "validated_pct", True)
        lo = _extreme(table, "validated_pct", False)
        out.append(
            f"Among the {len(table)} {label} with at least {min_n} registered companies, the "
            f"validated near-term share is highest in {hi['name']} ({fmt_pct(hi['validated_pct'])} "
            f"of {fmt_int(hi['n'])} companies) and lowest in {lo['name']} "
            f"({fmt_pct(lo['validated_pct'])} of {fmt_int(lo['n'])} companies)."
        )
        table = table.assign(gap=table["validated_pct"] - table["net_zero_pct"])
        big = _extreme(table, "gap", True)
        small = _extreme(table, "gap", False)
        out.append(
            f"The gap between validated near-term and validated net-zero share is widest in "
            f"{big['name']} ({fmt_pct(big['validated_pct'])} against "
            f"{fmt_pct(big['net_zero_pct'])}, {fmt_int(big['n'])} companies) and narrowest in "
            f"{small['name']} ({fmt_pct(small['validated_pct'])} against "
            f"{fmt_pct(small['net_zero_pct'])}, {fmt_int(small['n'])} companies)."
        )
        return out
    kpis = get_kpis(filtered)
    if kpis["companies"] >= min_n:
        out.append(
            f"In this selection, {fmt_pct(kpis['near_term_share'])} of "
            f"{fmt_int(kpis['companies'])} registered companies have validated near-term targets "
            f"and {fmt_pct(kpis['net_zero_share'])} have validated net-zero targets."
        )
    return out


def get_data_details(companies: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """Coverage of the whole data set, independent of any filter.

    The years run from the earliest to the latest year found in the company ``date_updated``
    and the target ``date_published`` fields.
    """
    stamps = pd.concat([companies["date_updated"], targets["date_published"]])
    years = stamps[stamps.str.fullmatch(r"\d{4}-\d{2}-\d{2}")].str[:4].astype(int)
    return {
        "first_year": int(years.min()),
        "last_year": int(years.max()),
        "locations": int(companies["location"].nunique()),
        "sectors": int(companies["sector"].nunique()),
        "regions": int(companies["region"].nunique()),
    }


def get_eda_summary(
    companies: pd.DataFrame, targets: pd.DataFrame, metadata: dict | None = None
) -> dict:
    """Descriptive summary of both tables, computed from the data passed in."""
    kpis = get_kpis(companies)
    per_company = targets.groupby("sbti_id").size()
    nz = status_counts(companies, "net_zero_status")
    nt = status_counts(companies, "near_term_status")
    top_locations = location_counts(companies, 10)
    top_sectors = _group_status(companies, "sector").head(10)
    comparison = location_target_comparison(companies, config.DEFAULT_MIN_N, top_n=10)
    return {
        "metadata": metadata or {},
        "rows": {"companies": len(companies), "targets": len(targets)},
        "columns": {"companies": len(companies.columns), "targets": len(targets.columns)},
        "distinct": {
            "companies": int(companies["sbti_id"].nunique()),
            "target_records": int(targets["row_entry_id"].nunique()),
            "locations": kpis["locations"],
            "sectors": kpis["sectors"],
            "regions": int(companies["region"].nunique()),
            "organization_types": int(companies["organization_type"].nunique()),
        },
        "company_kpis": kpis,
        "near_term_status": {
            r.status: {"companies": int(r.companies), "share_pct": r.share_pct}
            for r in nt.itertuples()
        },
        "net_zero_status": {
            r.status: {"companies": int(r.companies), "share_pct": r.share_pct}
            for r in nz.itertuples()
        },
        "target_records": summarize_target_records(targets),
        "target_status_other_records": int((targets["status"] == "Other").sum()),
        "records_per_company": {
            "min": int(per_company.min()),
            "median": float(per_company.median()),
            "mean": float(per_company.mean()),
            "max": int(per_company.max()),
        },  # fmt: skip
        "organization_type_counts": {
            k: int(v) for k, v in companies["organization_type"].value_counts().items()
        },
        "top_locations": top_locations.to_dict("records"),
        "top_sectors": top_sectors.to_dict("records"),
        "major_location_comparison": comparison.to_dict("records"),
        "date_updated": {
            "min": companies["date_updated"].min(),
            "max": companies["date_updated"].max(),
        },  # fmt: skip
    }
