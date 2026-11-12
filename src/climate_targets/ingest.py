"""Read the SBTi workbooks as they are, without type coercion, and describe them."""

from __future__ import annotations

import hashlib
from pathlib import Path

import openpyxl
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sheet_names(path: Path) -> list[str]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def read_sheet(path: Path, sheet: str) -> tuple[pd.DataFrame, int]:
    """Read one worksheet into an object-typed DataFrame.

    Values keep their Excel types (float, str, datetime, None). Pandas' own Excel reader
    is avoided because it turns the literal text ``NA`` and empty strings into missing values.

    Returns the DataFrame of named columns and the worksheet width in columns. Trailing
    columns without a header are dropped only if every cell in them is empty.
    """
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook[sheet].iter_rows(values_only=True)
        header = list(next(rows))
        width = len(header)
        body = [list(row) + [None] * (width - len(row)) for row in rows]
    finally:
        workbook.close()

    named = [i for i, name in enumerate(header) if name is not None]
    unnamed = [i for i, name in enumerate(header) if name is None]
    for i in unnamed:
        filled = [row[i] for row in body if row[i] not in (None, "")]
        if filled:
            raise ValueError(
                f"{path.name}: column {i + 1} has no header but contains {len(filled)} values"
            )
    names = [header[i] for i in named]
    if len(set(names)) != len(names):
        raise ValueError(f"{path.name}: duplicate column names in header")
    frame = pd.DataFrame([[row[i] for i in named] for row in body], columns=names, dtype=object)
    return frame, width


def read_dictionary(path: Path) -> dict[str, pd.DataFrame]:
    """Read every worksheet of the data dictionary as raw text-like frames."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        out = {}
        for ws in workbook.worksheets:
            data = [list(row) for row in ws.iter_rows(values_only=True)]
            out[ws.title] = pd.DataFrame(data, dtype=object)
        return out
    finally:
        workbook.close()
