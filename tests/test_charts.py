"""Chart figures contain exactly the numbers of the analysis tables they are built from."""

from __future__ import annotations

import pytest

from climate_targets import analysis, charts, config
from climate_targets.formatting import fmt_pct


def _trace(fig, name):
    return next(t for t in fig.data if t.name == name)


@pytest.mark.snapshot
def test_stacked_status_chart_matches_table_and_independent_recount(companies, reference):
    table = analysis.status_by_sector(companies, 10)
    fig = charts.status_by_sector_fig(table)
    names = [t.name for t in fig.data]
    assert names == ["Validated targets", "Commitment to set", "Commitment removed"]
    assert [t.marker.color for t in fig.data] == [
        config.COLOR_VALIDATED,
        config.COLOR_COMMITMENT,
        config.COLOR_REMOVED,
    ]
    sectors = list(fig.data[0].y)
    assert sectors == table["sector"].tolist()
    for i, sector in enumerate(sectors):
        total = sum(t.x[i] for t in fig.data)
        assert total == pytest.approx(100.0)  # segments total 100% within the sector
        ref = reference["by_sector"][sector]
        assert fig.data[0].x[i] == pytest.approx(
            100 * ref["near_term_validated"] / ref["companies"]
        )
        custom = fig.data[0].customdata[i]
        assert custom[1] == f"{ref['companies']:,}"  # group n in the tooltip
        assert custom[2] == fmt_pct(fig.data[0].x[i])  # tooltip text uses the shared rule
    assert "companies" in fig.data[0].hovertemplate and "Sector total" in fig.data[0].hovertemplate
    assert fig.layout.xaxis.range == (0, 100)
    assert "Share of SBTi-registered companies" in fig.layout.xaxis.title.text
    assert fig.layout.barmode == "stack"


def test_stacked_chart_is_sorted_largest_first(companies):
    table = analysis.status_by_sector(companies, 10)
    assert table["n"].tolist() == sorted(table["n"], reverse=True)
    assert len(table) == 10


@pytest.mark.snapshot
def test_location_ranking_chart(companies, reference):
    table = analysis.location_counts(companies, 10)
    fig = charts.location_rank_fig(table)
    assert list(fig.data[0].y) == table["location"].tolist()
    for loc, value in zip(fig.data[0].y, fig.data[0].x, strict=True):
        assert value == reference["by_location"][loc]["companies"]
    assert fig.layout.xaxis.title.text == charts.COUNT_AXIS_TITLE
    assert "registered companies" in fig.data[0].hovertemplate
    assert fig.data[0].marker.color == config.COLOR_BAR


@pytest.mark.snapshot
def test_paired_dot_chart_excludes_small_groups_and_uses_location_denominator(companies, reference):
    min_n = 500
    rows = charts.comparison_rows(analysis.location_target_comparison(companies, min_n), min_n)
    assert (rows["n"] >= min_n).all() and not rows.empty
    fig = charts.paired_dot_fig(rows)
    near, net = _trace(fig, "Near-term validated"), _trace(fig, "Net-zero validated")
    assert list(near.y) == list(net.y) == rows["location"].tolist()
    for loc, a, b in zip(near.y, near.x, net.x, strict=True):
        ref = reference["by_location"][loc]
        assert a == pytest.approx(100 * ref["near_term_validated"] / ref["companies"])
        assert b == pytest.approx(100 * ref["net_zero_validated"] / ref["companies"])
    for row in near.customdata:
        assert int(row[1].replace(",", "")) >= min_n
    assert near.marker.color == config.COLOR_VALIDATED and net.marker.color == config.COLOR_NET_ZERO
    assert "registered companies" in near.hovertemplate
    assert fig.layout.xaxis.title.text.startswith("Share of SBTi-registered companies")


def test_minimum_group_size_can_remove_every_location(companies):
    table = analysis.location_target_comparison(companies, 10**6)
    assert charts.comparison_rows(table, 10**6).empty


def test_target_charts_use_table_values(targets):
    types, _ = analysis.target_type_counts(targets)
    scopes, _ = analysis.scope_counts(targets)
    years, _ = analysis.target_year_counts(targets)
    assert list(charts.target_type_fig(types).data[0].x) == types["records"].tolist()
    assert list(charts.scope_fig(scopes).data[0].x) == scopes["records"].tolist()
    year_fig = charts.target_year_fig(years)
    assert list(year_fig.data[0].y) == years["records"].tolist()
    assert year_fig.layout.yaxis.title.text == "Target records (count)"


def test_chart_surfaces_are_transparent_on_the_dark_panel(companies):
    fig = charts.location_rank_fig(analysis.location_counts(companies, 5))
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert fig.data[0].marker.line.color == config.COLOR_PANEL
