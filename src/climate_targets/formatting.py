"""One formatting rule for counts and percentages, used by cards, tables, tooltips and text."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from . import config


def pct(numerator: float, denominator: float) -> float | None:
    """Percentage on a 0 to 100 scale, or ``None`` when the denominator is not positive."""
    if denominator is None or denominator <= 0:
        return None
    return 100.0 * numerator / denominator


def fmt_pct(value: float | None, decimals: int = 1) -> str:
    """Round half up to ``decimals`` places from the unrounded value. ``None`` gives ``n/a``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    quantum = Decimal(1).scaleb(-decimals)
    return f"{Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP)}%"


def fmt_int(value: int | float) -> str:
    return f"{int(value):,}"


def display_status(value: str) -> str:
    """Blank status is shown as ``Not recorded``. It is never read as a negative outcome."""
    return config.NOT_RECORDED if value == "" else value
