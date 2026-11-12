"""Load the processed CSV files with explicit types.

Every column is read as text and nothing is turned into a missing value, so that the
blank (``''``) and the literal ``NA`` stay distinct, exactly as written by the build.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config


class DataNotBuiltError(FileNotFoundError):
    """Raised when a processed file is missing."""


def read_processed(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DataNotBuiltError(
            f"{path.name} not found in {path.parent}. Build it with: python scripts/build_data.py"
        )
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])


def load_companies(path: Path = config.COMPANIES_CSV) -> pd.DataFrame:
    return read_processed(path)


def load_targets(path: Path = config.TARGETS_CSV) -> pd.DataFrame:
    return read_processed(path)


def write_processed(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n", encoding="utf-8")


def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    """CSV bytes for a download, UTF-8 with a byte order mark so spreadsheets show degree signs."""
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
