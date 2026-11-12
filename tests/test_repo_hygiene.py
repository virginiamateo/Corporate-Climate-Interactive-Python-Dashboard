"""Repository rules: independence of the recount, no placeholders, no hardcoded results."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [*sorted((ROOT / "src").rglob("*.py")), ROOT / "app.py"]


def test_independent_recount_does_not_import_the_package():
    text = (ROOT / "tests" / "independent_recount.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    imported |= {
        n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "climate_targets" not in imported
    assert "src" not in imported


def test_no_placeholders_in_source():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"TODO|FIXME|NotImplementedError", text), path
        assert not any(isinstance(n, ast.Pass) for n in ast.walk(ast.parse(text))), path


def test_no_audit_figures_are_hardcoded_in_source():
    reference = json.loads((ROOT / "tests" / "reference_values" / "snapshot.json").read_text())
    numbers = {
        reference["company_rows"],
        reference["target_rows"],
        reference["target_status_other_rows"],
        reference["company_net_zero_blank"],
        *reference["near_term_status"].values(),
        *[v for k, v in reference["net_zero_status"].items() if k != "(blank)"],
        *reference["target_action"].values(),
        reference["by_location"]["Japan"]["companies"],
        reference["by_location"]["Japan"]["near_term_validated"],
    }
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for number in numbers:
            assert not re.search(rf"(?<![\d.]){number}(?![\d.])", text), (path.name, number)


def test_gitignore_covers_private_and_data_paths():
    lines = {line.strip() for line in (ROOT / ".gitignore").read_text().splitlines()}
    for entry in ("planning/", "data/raw/*", "data/processed/*", ".venv/"):
        assert entry in lines, entry


def test_documentation_has_no_em_or_en_dashes():
    for name in ("README.md", "data/README.md", "tests/reference_values/README.md"):
        path = ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert "—" not in text and "–" not in text, name


def test_root_stays_clean():
    files = {p.name for p in ROOT.iterdir() if p.is_file()}
    allowed = {
        "README.md",
        "app.py",
        "pyproject.toml",
        "requirements.txt",
        ".gitignore",
        ".DS_Store",
    }
    assert files <= allowed, files - allowed
