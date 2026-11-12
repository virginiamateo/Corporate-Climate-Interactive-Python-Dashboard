"""Corporate Climate Targets Explorer: Streamlit entry point.

Layout and widget wiring only. Calculations live in climate_targets.analysis.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from climate_targets import analysis, config, datasets, validate
from climate_targets.theme import inject_css
from climate_targets.views import explorer, overview, quality

st.set_page_config(layout="wide", page_title="Corporate Climate Targets Explorer")
inject_css()

FILTERS = {
    "location": ("Location", "f_location"),
    "sector": ("Sector", "f_sector"),
    "organization_type": ("Organisation type", "f_org"),
}


@st.cache_data(show_spinner="Loading data")
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return datasets.load_companies(), datasets.load_targets()


@st.cache_data(show_spinner=False)
def run_checks(_companies: pd.DataFrame, _targets: pd.DataFrame) -> list[validate.CheckResult]:
    return validate.run_all_checks(_companies, _targets)


@st.cache_data(show_spinner=False)
def explorer_tables(
    _companies: pd.DataFrame,
    _targets: pd.DataFrame,
    locations: tuple,
    sectors: tuple,
    organization_types: tuple,
) -> explorer.ExplorerTables:
    filtered = analysis.filter_companies(_companies, locations, sectors, organization_types)
    return explorer.build_explorer_tables(filtered, _targets)


def reset_filters() -> None:
    for _, key in FILTERS.values():
        st.session_state[key] = []
    st.session_state["min_n"] = config.DEFAULT_MIN_N
    st.session_state["company_query"] = ""


def main() -> None:
    try:
        companies, targets = load_data()
    except datasets.DataNotBuiltError as error:
        st.error(str(error))
        st.stop()
        return

    with st.sidebar:
        st.markdown("### Filters")
        selected = {}
        for field, (label, key) in FILTERS.items():
            options = sorted(companies[field].unique())
            selected[field] = st.multiselect(label, options, key=key, placeholder="All")
        st.session_state.setdefault("min_n", config.DEFAULT_MIN_N)
        st.number_input(
            "Minimum companies per group (paired chart)",
            min_value=1,
            max_value=500,
            step=5,
            key="min_n",
            help="Locations with fewer registered companies are left out of the "
            "near-term versus net-zero comparison.",
        )
        st.button("Reset filters", on_click=reset_filters, key="reset_filters")
        st.divider()
        st.caption(
            "The SBTi directory is voluntary. Every figure describes companies in the "
            "directory, not all companies in a sector or country."
        )

    filtered = analysis.filter_companies(
        companies, selected["location"], selected["sector"], selected["organization_type"]
    )
    min_n = int(st.session_state.get("min_n", config.DEFAULT_MIN_N))
    latest = companies["date_updated"].max()
    st.caption(
        f"Source: Science Based Targets initiative, Target Dashboard files. Voluntary "
        f"directory. Latest company update in the file: {latest}. See the Data quality tab for "
        "file details."
    )

    checks = run_checks(companies, targets)
    tab_overview, tab_explorer, tab_quality = st.tabs(
        ["Overview", "Company and target explorer", "Data quality and methodology"]
    )
    with tab_overview:
        overview.render(filtered, checks, min_n, analysis.get_data_details(companies, targets))
    with tab_explorer:
        tables = explorer_tables(
            companies,
            targets,
            tuple(selected["location"]),
            tuple(selected["sector"]),
            tuple(selected["organization_type"]),
        )
        explorer.render(filtered, targets, tables)
    with tab_quality:
        quality.render(checks)


main()
