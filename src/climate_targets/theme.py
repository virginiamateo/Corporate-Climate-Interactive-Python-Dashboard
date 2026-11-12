"""Small stylesheet and table styling for the terminal-style look.

The page theme itself is in ``.streamlit/config.toml``. The rules here cover only what the
theme options cannot: orange panel title bars, the orange selected tab, orange card values
and uppercase headings. Colours come from ``config``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import config

CSS = f"""
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stSidebar"] h3 {{
    color: {config.COLOR_ORANGE} !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
[data-testid="stMetricValue"] {{ color: {config.COLOR_ORANGE}; }}
[data-testid="stMetricLabel"] p {{
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
[data-testid="stTab"] {{ padding: 0.4rem 1rem; }}
[data-testid="stTab"][aria-selected="true"] {{ background: {config.COLOR_ORANGE}; }}
[data-testid="stTab"][aria-selected="true"] p {{ color: #000000; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: {config.COLOR_PANEL}; }}
.ct-byline {{
    color: {config.COLOR_ORANGE};
    font-size: 1.5rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: -0.4rem 0 0.8rem 0;
}}
.ct-detail-label {{
    color: {config.COLOR_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.85rem;
}}
.ct-detail-value {{
    color: {config.COLOR_ORANGE};
    font-size: 1.6rem;
    line-height: 1.3;
}}
.ct-panel-title {{
    background: {config.COLOR_ORANGE};
    color: #000000;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.35rem 0.9rem;
    margin: -1rem -1rem 0.6rem -1rem;
}}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def byline_html(text: str) -> str:
    return f'<div class="ct-byline">{text}</div>'


def detail_html(label: str, value: str) -> str:
    return f'<div class="ct-detail-label">{label}</div><div class="ct-detail-value">{value}</div>'


def panel_title_html(title: str) -> str:
    return f'<div class="ct-panel-title">{title}</div>'


def style_result_column(frame: pd.DataFrame, column: str = "Result"):
    """Pandas Styler that colours Pass green and Fail coral in ``column``."""

    def colour(value: str) -> str:
        return f"color: {config.COLOR_GREEN if value == 'Pass' else config.COLOR_CORAL}"

    return frame.style.map(colour, subset=[column])
