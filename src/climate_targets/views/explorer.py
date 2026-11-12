"""Company and target explorer tab."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from .. import analysis, charts, datasets
from ..formatting import fmt_int
from .overview import NO_MATCH, PLOT_CONFIG


@dataclass
class ExplorerTables:
    """The frames shown in the explorer and the CSV bytes exported from those same frames."""

    companies: pd.DataFrame
    targets: pd.DataFrame
    companies_csv: bytes
    targets_csv: bytes


def build_explorer_tables(filtered: pd.DataFrame, targets: pd.DataFrame) -> ExplorerTables:
    shown_companies = analysis.company_display_table(filtered)
    shown_targets = analysis.target_display_table(analysis.filter_targets(targets, filtered))
    return ExplorerTables(
        shown_companies, shown_targets,
        datasets.to_csv_bytes(shown_companies), datasets.to_csv_bytes(shown_targets),
    )  # fmt: skip


def _company_label(row: pd.Series) -> str:
    return f"{row['company_name']} ({row['sbti_id']}, {row['location']})"


def render(filtered: pd.DataFrame, targets: pd.DataFrame, tables: ExplorerTables) -> None:
    st.header("Company and target explorer", anchor=False)
    if filtered.empty:
        st.info(NO_MATCH)
        return

    st.subheader("Look up a company", anchor=False)
    query = st.text_input(
        "Search by company name or SBTi ID (within the current filters)", key="company_query"
    )
    matches = analysis.search_companies(filtered, query)
    if query.strip() and matches.empty:
        st.info("No company in the current selection matches that search.")
    elif not matches.empty:
        labels = {row["sbti_id"]: _company_label(row) for _, row in matches.iterrows()}
        chosen = st.selectbox(
            f"{len(matches)} matching companies"
            + (" (first 50 shown)" if len(matches) == 50 else ""),
            options=list(labels),
            format_func=labels.get,
            key="company_choice",
        )
        company = filtered[filtered["sbti_id"] == chosen].iloc[0]
        records = analysis.get_company_target_records(targets, filtered, chosen)
        shown = analysis.company_display_table(filtered[filtered["sbti_id"] == chosen]).iloc[0]
        with st.container(border=True):
            st.markdown(f"**{company['company_name']}** (SBTi ID {company['sbti_id']})")
            c = st.columns(4)
            c[0].markdown(f"Location  \n{shown['location']}")
            c[1].markdown(f"Sector  \n{shown['sector']}")
            c[2].markdown(f"Near-term status  \n{shown['near_term_status']}")
            c[3].markdown(f"Net-zero status  \n{shown['net_zero_status']}")
            st.caption(
                f"{len(records)} target and commitment records. Company data last updated "
                f"{company['date_updated']}."
            )
            st.dataframe(
                analysis.target_display_table(records),
                hide_index=True,
                width="stretch",
                key="selected_company_records",
            )

    st.subheader("Companies in the current selection", anchor=False)
    st.caption(
        f"{fmt_int(len(tables.companies))} registered companies, one row per SBTi ID. "
        "Use the table toolbar to search within the rows."
    )
    st.dataframe(tables.companies, hide_index=True, width="stretch", key="companies_table")
    st.download_button(
        "Download companies (CSV)",
        tables.companies_csv,
        file_name="companies_selection.csv",
        mime="text/csv",
        key="download_companies",
        on_click="ignore",
    )

    st.subheader("Target and commitment records for these companies", anchor=False)
    st.caption(
        f"{fmt_int(len(tables.targets))} records, one row per target or commitment "
        "(a company can have several). Records are not companies."
    )
    st.dataframe(tables.targets, hide_index=True, width="stretch", key="targets_table")
    st.download_button(
        "Download target records (CSV)",
        tables.targets_csv,
        file_name="target_records_selection.csv",
        mime="text/csv",
        key="download_targets",
        on_click="ignore",
    )

    with st.expander("Target types, scopes and target years (Target records only)"):
        records = analysis.filter_targets(targets, filtered)
        st.caption(
            "Commitment records are left out. Records without a recorded value are "
            "excluded from each count and not imputed."
        )
        c1, c2 = st.columns(2)
        types, no_type = analysis.target_type_counts(records)
        scopes, no_scope = analysis.scope_counts(records)
        years, no_year = analysis.target_year_counts(records)
        with c1:
            st.markdown("**Target type**")
            if types.empty:
                st.info("No target records in this selection.")
            else:
                st.plotly_chart(
                    charts.target_type_fig(types), theme=None, config=PLOT_CONFIG, key="chart_type"
                )
                st.caption(f"{no_type} target records have no recorded type.")
        with c2:
            st.markdown("**Scope covered**")
            if scopes.empty:
                st.info("No target records in this selection.")
            else:
                st.plotly_chart(
                    charts.scope_fig(scopes), theme=None, config=PLOT_CONFIG, key="chart_scope"
                )
                st.caption(f"{no_scope} target records have no recorded scope.")
        st.markdown("**Target year**")
        if years.empty:
            st.info("No target records with a recorded target year in this selection.")
        else:
            st.plotly_chart(
                charts.target_year_fig(years), theme=None, config=PLOT_CONFIG, key="chart_year"
            )
            st.caption(
                f"{fmt_int(no_year)} target records have no recorded target year and are "
                "excluded. FY and CY prefixes are removed to give the numeric year."
            )
