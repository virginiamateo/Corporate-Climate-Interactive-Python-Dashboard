"""Overview tab: KPI cards, sector status, location ranking, paired-dot comparison, findings."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import analysis, charts, config, validate
from ..formatting import fmt_int, fmt_pct
from ..theme import byline_html, detail_html, panel_title_html, style_result_column

PLOT_CONFIG = {"displayModeBar": False}
NO_MATCH = "No records match the selected filters"


def kpi_row(filtered: pd.DataFrame) -> None:
    k = analysis.get_kpis(filtered)
    cols = st.columns(4)
    n = k["companies"]
    with cols[0]:
        st.metric("Registered companies", fmt_int(n), border=True)
        st.caption("Unique SBTi IDs in the current selection")
    with cols[1]:
        st.metric("Validated near-term", fmt_pct(k["near_term_share"]), border=True)
        st.caption(f"{fmt_int(k['near_term_validated'])} of {fmt_int(n)} registered companies")
    with cols[2]:
        st.metric("Validated net-zero", fmt_pct(k["net_zero_share"]), border=True)
        st.caption(f"{fmt_int(k['net_zero_validated'])} of {fmt_int(n)} registered companies")
    with cols[3]:
        st.metric("Geographic locations", fmt_int(k["locations"]), border=True)
        st.caption("Unique location values (territories included)")


def _panel(title: str, caption: str):
    box = st.container(border=True)
    box.markdown(panel_title_html(title), unsafe_allow_html=True)
    box.caption(caption)
    return box


def render(
    filtered: pd.DataFrame, checks: list[validate.CheckResult], min_n: int, details: dict
) -> None:
    st.header("Corporate Climate Targets Explorer", anchor=False)
    st.markdown(byline_html(config.PROJECT_BYLINE), unsafe_allow_html=True)
    st.markdown(f"**Research question:** {config.RESEARCH_QUESTION}")

    if filtered.empty:
        st.info(NO_MATCH)
        return

    kpi_row(filtered)

    left, right = st.columns(2)
    with left:
        box = _panel(
            "Near-term target status by sector",
            "Top 10 sectors by registered companies. Each bar is 100% of the registered "
            "companies in that sector.",
        )
        box.plotly_chart(
            charts.status_by_sector_fig(analysis.status_by_sector(filtered, 10)),
            theme=None,
            config=PLOT_CONFIG,
            key="chart_sector",
        )
    with right:
        box = _panel(
            "Registered companies by location",
            "Top 10 locations by number of SBTi-registered companies. This is the size of the "
            "directory, not a participation rate among all companies.",
        )
        box.plotly_chart(
            charts.location_rank_fig(analysis.location_counts(filtered, 10)),
            theme=None,
            config=PLOT_CONFIG,
            key="chart_location",
        )

    left, right = st.columns([3, 2])
    with left:
        box = _panel(
            "Near-term versus net-zero validation by location",
            f"Locations with at least {min_n} registered companies, largest first. Both shares "
            "use the registered companies in that location as the denominator. The two "
            "statuses overlap and are different concepts.",
        )
        rows = charts.comparison_rows(analysis.location_target_comparison(filtered, min_n), min_n)
        if rows.empty:
            box.info(f"No location in this selection has at least {min_n} registered companies.")
        else:
            box.plotly_chart(
                charts.paired_dot_fig(rows), theme=None, config=PLOT_CONFIG, key="chart_paired"
            )
    with right:
        box = _panel(
            "Findings for this selection",
            "Calculated from the filtered companies. Descriptive only.",
        )
        statements = analysis.build_insights(filtered, min_n)
        if statements:
            for text in statements:
                box.markdown(f"- {text}")
        else:
            box.write(
                f"No comparison applies: fewer than two groups have at least {min_n} registered "
                "companies and the selection itself is smaller than that."
            )
        box = _panel(
            "Data checks", "Whole directory, independent of the filters. Every count should be 0."
        )
        wanted = {
            "company_ids_unique": "Duplicate company IDs",
            "orphan_target_records": "Unmatched target records",
            "companies_without_targets": "Companies without records",
            "target_row_ids_unique": "Duplicate record IDs",
        }
        table = pd.DataFrame(
            [
                {
                    "Check": wanted[r.name],
                    "Count": r.count,
                    "Result": "Pass" if r.passed else "Fail",
                }
                for r in checks
                if r.name in wanted
            ]
        )
        box.dataframe(style_result_column(table), hide_index=True, width="stretch")

    box = _panel(
        "Data details",
        "The whole data set, independent of the filters.",
    )
    items = [
        ("Years covered", f"{details['first_year']} to {details['last_year']}"),
        ("Locations", fmt_int(details["locations"])),
        ("Sectors", fmt_int(details["sectors"])),
        ("Regions", fmt_int(details["regions"])),
    ]
    for column, (label, value) in zip(box.columns(len(items)), items, strict=True):
        column.markdown(detail_html(label, value), unsafe_allow_html=True)

    st.caption(
        "The SBTi directory is voluntary and covers companies that chose to register, so shares "
        "describe directory companies only. A validated target is not evidence that emissions "
        "have fallen. Source: Science Based Targets initiative, Target Dashboard files. The "
        "latest SBTi website figures can differ from this file snapshot."
    )
