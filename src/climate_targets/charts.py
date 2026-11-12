"""Plotly figure constructors. Each takes a table from ``analysis`` and returns a Figure.

No file access and no Streamlit calls. Percent strings shown in tooltips and labels come
from ``formatting.fmt_pct`` so charts, cards and tables use one rounding rule.
"""

from __future__ import annotations

import textwrap

import pandas as pd
import plotly.graph_objects as go

from . import config
from .formatting import fmt_int, fmt_pct

FONT = "Menlo, Consolas, DejaVu Sans Mono, Courier New, monospace"

COUNT_AXIS_TITLE = "Registered companies (count)"
SHARE_AXIS_TITLE = "Share of SBTi-registered companies<br>in this group (%)"

LEGEND_LABELS = {
    "validated": "Validated targets",
    "commitment": "Commitment to set",
    "removed": "Commitment removed",
}


def _wrap(label: str, width: int = 32) -> str:
    return "<br>".join(textwrap.wrap(label, width=width, break_long_words=False)) or label


def _base_layout(height: int, left: int = 190, right: int = 24, top: int = 36) -> dict:
    return {
        "height": height,
        "margin": {"l": left, "r": right, "t": top, "b": 72},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": FONT, "size": 11, "color": config.COLOR_TEXT},
        "hoverlabel": {
            "bgcolor": config.COLOR_BG,
            "font": {"family": FONT, "size": 11, "color": config.COLOR_TEXT},
            "bordercolor": config.COLOR_ORANGE,
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.0,
            "xanchor": "left",
            "x": 0,
            "traceorder": "normal",
            "font": {"size": 12, "color": config.COLOR_TEXT},
        },
    }


def _axes(fig: go.Figure, x_title: str, x_range=None, x_ticksuffix: str = "") -> None:
    fig.update_xaxes(
        title={"text": x_title, "font": {"size": 11, "color": config.COLOR_MUTED}},
        range=x_range,
        ticksuffix=x_ticksuffix,
        gridcolor=config.COLOR_GRID,
        gridwidth=1,
        zeroline=False,
        showline=False,
        tickfont={"color": config.COLOR_MUTED},
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=False,
        zeroline=False,
        showline=False,
        tickfont={"color": config.COLOR_TEXT, "size": 11},
        ticklen=0,
    )


def status_by_sector_fig(table: pd.DataFrame) -> go.Figure:
    """100% stacked horizontal bars of near-term status for each sector in ``table``.

    Each bar sums to the registered companies of that sector. Largest sector on top.
    """
    fig = go.Figure()
    sectors = table["sector"].tolist()
    segments = [("validated", config.COLOR_VALIDATED), ("commitment", config.COLOR_COMMITMENT),
                ("removed", config.COLOR_REMOVED)]  # fmt: skip
    for name, color in segments:
        pct_text = [fmt_pct(v) for v in table[f"{name}_pct"]]
        custom = list(zip(table[name].map(fmt_int), table["n"].map(fmt_int), pct_text, strict=True))
        fig.add_trace(
            go.Bar(
                name=LEGEND_LABELS[name],
                y=sectors,
                x=table[f"{name}_pct"],
                orientation="h",
                marker={"color": color, "line": {"color": config.COLOR_PANEL, "width": 2}},
                customdata=custom,
                text=pct_text if name == "validated" else None,
                textposition="inside",
                insidetextanchor="start",
                textfont={"color": config.COLOR_BG, "size": 12},
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    + LEGEND_LABELS[name]
                    + ": %{customdata[0]} companies (%{customdata[2]})<br>"
                    "Sector total: %{customdata[1]} registered companies<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        **_base_layout(height=max(220, 80 + 54 * len(sectors)), left=250),
        barmode="stack",
        bargap=0.35,
    )
    _axes(fig, SHARE_AXIS_TITLE.replace("this group", "the sector"), [0, 100], "%")
    fig.update_yaxes(tickmode="array", tickvals=sectors, ticktext=[_wrap(s) for s in sectors])
    return fig


def location_rank_fig(table: pd.DataFrame) -> go.Figure:
    """Horizontal ranking bars: registered companies per location (directory size)."""
    locations = table["location"].tolist()
    share = [fmt_pct(v) for v in table["share_of_selection_pct"]]
    fig = go.Figure(
        go.Bar(
            y=locations,
            x=table["companies"],
            orientation="h",
            marker={"color": config.COLOR_BAR, "line": {"color": config.COLOR_PANEL, "width": 2}},
            text=table["companies"].map(fmt_int),
            textposition="outside",
            cliponaxis=False,
            textfont={"color": config.COLOR_TEXT, "size": 12},
            customdata=list(zip(table["companies"].map(fmt_int), share, strict=True)),
            hovertemplate=(
                "<b>%{y}</b><br>%{customdata[0]} registered companies<br>"
                "%{customdata[1]} of the companies in the current selection"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )
    fig.update_layout(
        **_base_layout(height=max(220, 80 + 54 * len(locations)), left=230, right=60), bargap=0.35
    )
    _axes(fig, COUNT_AXIS_TITLE)
    fig.update_xaxes(rangemode="tozero")
    fig.update_yaxes(
        tickmode="array", tickvals=locations, ticktext=[_wrap(v, 30) for v in locations]
    )
    return fig


def comparison_rows(table: pd.DataFrame, min_n: int, top_n: int = 10) -> pd.DataFrame:
    """Locations that meet the minimum group size, largest first, limited to ``top_n``."""
    return table[table["n"] >= min_n].head(top_n).reset_index(drop=True)


def paired_dot_fig(rows: pd.DataFrame) -> go.Figure:
    """Near-term and net-zero validated share per location, joined by a thin line.

    ``rows`` must already be restricted to groups that meet the minimum size (see
    ``comparison_rows``). Both shares use the registered companies of that location.
    """
    locations = rows["location"].tolist()
    fig = go.Figure()
    xs, ys = [], []
    for loc, a, b in zip(locations, rows["near_term_pct"], rows["net_zero_pct"], strict=True):
        xs += [a, b, None]
        ys += [loc, loc, None]
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            line={"color": config.COLOR_MUTED, "width": 2},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    def dots(name, values, counts, color, other):
        text = [fmt_pct(v) for v in values]
        position = [
            "middle left" if v <= o else "middle right" for v, o in zip(values, other, strict=True)
        ]
        fig.add_trace(
            go.Scatter(
                name=name,
                x=values,
                y=locations,
                mode="markers+text",
                text=text,
                textposition=position,
                textfont={"color": config.COLOR_TEXT, "size": 12},
                marker={
                    "color": color,
                    "size": 12,
                    "line": {"color": config.COLOR_PANEL, "width": 2},
                },
                customdata=list(
                    zip(counts.map(fmt_int), rows["n"].map(fmt_int), text, strict=True)
                ),
                hovertemplate=(
                    "<b>%{y}</b><br>" + name + ": %{customdata[2]}<br>"
                    "%{customdata[0]} of %{customdata[1]} registered companies"
                    "<extra></extra>"
                ),
            )
        )

    dots(
        "Near-term validated",
        rows["near_term_pct"],
        rows["near_term_validated"],
        config.COLOR_VALIDATED,
        rows["net_zero_pct"],
    )
    dots(
        "Net-zero validated",
        rows["net_zero_pct"],
        rows["net_zero_validated"],
        config.COLOR_NET_ZERO,
        rows["near_term_pct"],
    )
    fig.update_layout(
        **_base_layout(height=max(240, 100 + 54 * len(locations)), left=230, right=40)
    )
    _axes(fig, SHARE_AXIS_TITLE.replace("this group", "the location"), [-14, 114], "%")
    fig.update_xaxes(tickvals=[0, 20, 40, 60, 80, 100])
    fig.update_yaxes(
        tickmode="array", tickvals=locations, ticktext=[_wrap(v, 30) for v in locations]
    )
    return fig


def _simple_bar(
    table: pd.DataFrame, category: str, x_title: str, horizontal: bool = True
) -> go.Figure:
    labels = table[category].astype(str).tolist()
    fig = go.Figure(
        go.Bar(
            x=table["records"] if horizontal else labels,
            y=labels if horizontal else table["records"],
            orientation="h" if horizontal else "v",
            marker={"color": config.COLOR_BAR, "line": {"color": config.COLOR_PANEL, "width": 2}},
            text=table["records"].map(fmt_int),
            textposition="outside",
            cliponaxis=False,
            textfont={"color": config.COLOR_TEXT, "size": 12},
            hovertemplate="<b>%{" + ("y" if horizontal else "x") + "}</b><br>%{text} target records"
            "<extra></extra>",
            showlegend=False,
        )
    )
    height = max(220, 70 + 36 * len(labels)) if horizontal else 340
    fig.update_layout(**_base_layout(height=height, left=160 if horizontal else 56, right=60))
    if horizontal:
        _axes(fig, x_title)
        fig.update_xaxes(rangemode="tozero")
    else:
        fig.update_xaxes(
            title={
                "text": category.replace("_", " ").capitalize(),
                "font": {"size": 12, "color": config.COLOR_MUTED},
            },
            type="category",
            showgrid=False,
            tickfont={"color": config.COLOR_MUTED},
        )
        fig.update_yaxes(
            title={"text": x_title, "font": {"size": 11, "color": config.COLOR_MUTED}},
            gridcolor=config.COLOR_GRID,
            zeroline=False,
            rangemode="tozero",
            tickfont={"color": config.COLOR_MUTED},
        )
    return fig


def target_type_fig(table: pd.DataFrame) -> go.Figure:
    return _simple_bar(table, "type", "Target records (count)")


def scope_fig(table: pd.DataFrame) -> go.Figure:
    return _simple_bar(table, "scope", "Target records (count)")


def target_year_fig(table: pd.DataFrame) -> go.Figure:
    return _simple_bar(table, "target_year", "Target records (count)", horizontal=False)
