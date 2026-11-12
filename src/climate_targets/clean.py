"""Deterministic cleaning of the raw company and target frames.

Every transformation is recorded in a change log with the number of values it changed.
Raw values that are transformed are kept in ``*_raw`` columns so the change can be audited.
Blank (empty string) and the literal text ``NA`` stay distinct throughout.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd

from . import config

# Columns holding identifiers or categories on which joins, filters and groupings depend.
# Free-text columns (target wording and similar) are not touched.
COMPANY_TEXT_KEY_COLUMNS = [
    "company_name", "organization_type", "location", "region", "sector",
    "near_term_status", "long_term_status", "net_zero_status",
]  # fmt: skip
TARGET_TEXT_KEY_COLUMNS = [
    "company_name", "organization_type", "location", "region", "sector",
    "action", "status", "year_type",
]  # fmt: skip

COMPANY_YEAR_COLUMNS = ["near_term_target_year", "long_term_target_year", "net_zero_year"]
TARGET_YEAR_COLUMNS = ["base_year", "target_year"]
COMPANY_DATE_COLUMNS = ["ba15_date", "date_updated"]
TARGET_DATE_COLUMNS = ["commitment_deadline", "date_published"]

_ID_RE = re.compile(config.SBTI_ID_PATTERN)
_YEAR_RE = re.compile(r"^(?:FY|CY)?\d{4}$")
_PLAIN_YEAR_RE = re.compile(r"^\d{4}$")


@dataclass
class Change:
    """One entry of the change log."""

    rule: str
    table: str
    column: str
    examined: int
    changed: int
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class IdError(ValueError):
    """Raised when an SBTi identifier cannot be normalised exactly."""


def normalize_sbti_id(value: object) -> str:
    """Return the exact eight-digit ID string for an Excel numeric or text identifier.

    Accepts integral floats, ints, and numeric text including scientific notation.
    Rejects missing, non-integral, ambiguous and out-of-range values.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise IdError("missing SBTi ID")
    if isinstance(value, bool):
        raise IdError(f"invalid SBTi ID {value!r}")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IdError(f"non-finite SBTi ID {value!r}")
        number = Decimal(repr(value))
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str):
        try:
            number = Decimal(value.strip())
        except InvalidOperation as exc:
            raise IdError(f"unparseable SBTi ID {value!r}") from exc
    else:
        raise IdError(f"unsupported SBTi ID type {type(value).__name__}")
    if number != number.to_integral_value():
        raise IdError(f"non-integral SBTi ID {value!r}")
    text = str(int(number))
    if not _ID_RE.match(text):
        raise IdError(f"SBTi ID {value!r} is not an eight-digit ID starting with 4")
    return text


def normalize_year(value: object) -> tuple[str, bool]:
    """Return (cleaned text, changed). Only integer-like numbers are rewritten.

    ``2030.0`` becomes ``2030``. Text such as ``FY2030``, ``2030``, ``NA`` and ``''``
    is returned unchanged. A number that is not an integer is rejected.
    """
    if isinstance(value, bool):
        raise ValueError(f"invalid year {value!r}")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not (math.isfinite(value) and value.is_integer()):
            raise ValueError(f"non-integer year {value!r}")
        return str(int(value)), True
    if value is None:
        return "", True
    return str(value), False


def normalize_scope(value: object) -> tuple[str, bool]:
    """Return (cleaned text, changed). ``1.0``, ``2.0``, ``3.0`` become ``1``, ``2``, ``3``.

    Multi-scope text such as ``1+2`` is preserved. Other numbers are rejected.
    """
    if isinstance(value, bool):
        raise ValueError(f"invalid scope {value!r}")
    if isinstance(value, (int, float)):
        if float(value) in (1.0, 2.0, 3.0):
            return str(int(value)), True
        raise ValueError(f"ambiguous numeric scope {value!r}")
    if value is None:
        return "", True
    return str(value), False


def normalize_date(value: object) -> tuple[str, bool]:
    """Return (ISO date text, changed).

    ``datetime`` cells become ``YYYY-MM-DD``. Numeric Excel serials are converted from
    the 1899-12-30 origin. Text such as ``NA`` or ``''`` is returned unchanged.
    """
    if isinstance(value, dt.datetime):
        return value.date().isoformat(), True
    if isinstance(value, dt.date):
        return value.isoformat(), True
    if isinstance(value, bool):
        raise ValueError(f"invalid date {value!r}")
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or not 1 <= float(value) < 109_575:  # to year 2199
            raise ValueError(f"Excel serial out of range {value!r}")
        stamp = pd.Timestamp(config.EXCEL_EPOCH) + pd.to_timedelta(float(value), unit="D")
        return stamp.date().isoformat(), True
    if value is None:
        return "", True
    return str(value), False


def _strip(value: object) -> str:
    return value.strip() if isinstance(value, str) else value  # type: ignore[return-value]


def _apply(
    frame: pd.DataFrame,
    table: str,
    column: str,
    func,
    rule: str,
    log: list[Change],
    keep_raw: bool = False,
    note: str = "",
) -> None:
    """Apply a (value -> (text, changed)) function to one column and log the result."""
    original = frame[column]
    results = [func(v) for v in original]
    cleaned = [r[0] for r in results]
    changed = sum(1 for r in results if r[1])
    if keep_raw:
        frame[f"{column}_raw"] = original
    frame[column] = cleaned
    log.append(Change(rule, table, column, len(frame), changed, note))


def _blank_none(frame: pd.DataFrame, table: str, log: list[Change]) -> None:
    for column in frame.columns:
        count = int(frame[column].isna().sum())
        if count:
            frame[column] = frame[column].where(frame[column].notna(), "")
            log.append(
                Change("none_to_blank", table, column, len(frame), count, "empty cell to ''")
            )


def _strip_columns(frame: pd.DataFrame, table: str, columns: list[str], log: list[Change]) -> None:
    for column in columns:
        before = frame[column]
        after = before.map(_strip)
        changed = int((before != after).sum())
        frame[column] = after
        log.append(
            Change("strip_whitespace", table, column, len(frame), changed, "leading/trailing only")
        )


def _year_checks(frame: pd.DataFrame, table: str, columns: list[str], log: list[Change]) -> None:
    for column in columns:
        bad = [v for v in frame[column] if v not in ("", "NA") and not _YEAR_RE.match(v)]
        log.append(
            Change(
                "flag_unrecognised_year", table, column, len(frame), 0,
                f"{len(bad)} values not matching [FY|CY]yyyy, left unchanged",
            )
        )  # fmt: skip


def clean_companies(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[Change]]:
    """Clean the company frame. One row per registered company."""
    log: list[Change] = []
    frame = raw.copy()
    table = "companies"
    _blank_none(frame, table, log)

    ids = [normalize_sbti_id(v) for v in frame["sbti_id"]]
    changed = sum(1 for a, b in zip(frame["sbti_id"], ids, strict=True) if a != b)
    frame["sbti_id_raw"] = frame["sbti_id"]
    frame["sbti_id"] = ids
    log.append(Change("normalize_sbti_id", table, "sbti_id", len(frame), changed, "float to text"))

    _strip_columns(frame, table, COMPANY_TEXT_KEY_COLUMNS, log)
    for column in COMPANY_YEAR_COLUMNS:
        _apply(frame, table, column, normalize_year, "normalize_year", log)
    _year_checks(frame, table, COMPANY_YEAR_COLUMNS, log)
    for column in COMPANY_DATE_COLUMNS:
        _apply(frame, table, column, normalize_date, "normalize_date", log, note="to ISO date")

    for column in frame.columns:
        frame[column] = frame[column].astype(str)
    frame = frame.sort_values("sbti_id", kind="mergesort").reset_index(drop=True)
    return frame, log


def clean_targets(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[Change]]:
    """Clean the target frame. One row per target or commitment record."""
    log: list[Change] = []
    frame = raw.copy()
    table = "targets"
    _blank_none(frame, table, log)

    ids = [normalize_sbti_id(v) for v in frame["sbti_id"]]
    changed = sum(1 for a, b in zip(frame["sbti_id"], ids, strict=True) if a != b)
    frame["sbti_id_raw"] = frame["sbti_id"]
    frame["sbti_id"] = ids
    log.append(Change("normalize_sbti_id", table, "sbti_id", len(frame), changed, "float to text"))

    _strip_columns(frame, table, ["row_entry_id", *TARGET_TEXT_KEY_COLUMNS], log)
    for column in TARGET_YEAR_COLUMNS:
        _apply(frame, table, column, normalize_year, "normalize_year", log, keep_raw=True)
    _year_checks(frame, table, TARGET_YEAR_COLUMNS, log)
    _apply(frame, table, "scope", normalize_scope, "normalize_scope", log, keep_raw=True)
    for column in TARGET_DATE_COLUMNS:
        _apply(frame, table, column, normalize_date, "normalize_date", log, note="to ISO date")

    for column in frame.columns:
        frame[column] = frame[column].astype(str)
    frame = frame.sort_values("row_entry_id", kind="mergesort").reset_index(drop=True)
    return frame, log


def target_year_number(series: pd.Series) -> pd.Series:
    """Numeric year (Int64) from cleaned year text. FY and CY prefixes are removed.

    ``''`` and ``NA`` become missing. The prefix is not lost in the processed file because
    this is computed on demand from the text column.
    """
    digits = series.str.extract(r"(\d{4})$", expand=False)
    return pd.to_numeric(digits).astype("Int64")


def change_log_frame(log: list[Change]) -> pd.DataFrame:
    return pd.DataFrame([c.as_dict() for c in log])
