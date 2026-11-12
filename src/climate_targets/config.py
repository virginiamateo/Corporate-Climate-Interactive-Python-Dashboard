"""Paths, canonical schema, labels and colours shared across the project."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"

COMPANIES_XLSX = RAW_DIR / "companies-excel.xlsx"
TARGETS_XLSX = RAW_DIR / "targets-excel.xlsx"
DICTIONARY_XLSX = RAW_DIR / "Alpha-Dashboard-Data-Dictionary.xlsx"

COMPANIES_CSV = PROCESSED_DIR / "companies.csv"
TARGETS_CSV = PROCESSED_DIR / "targets.csv"

COMPANIES_SHEET = "Data"
TARGETS_SHEET = "WebsiteData"

SOURCE_URLS = {
    "companies-excel.xlsx": "https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx",
    "targets-excel.xlsx": "https://files.sciencebasedtargets.org/production/files/targets-excel.xlsx",
    "Alpha-Dashboard-Data-Dictionary.xlsx": (
        "https://files.sciencebasedtargets.org/production/files/Alpha-Dashboard-Data-Dictionary.xlsx"
    ),
}
SOURCE_PAGE = "https://sciencebasedtargets.org/target-dashboard"

COMPANY_COLUMNS = [
    "sbti_id", "company_name", "isin", "lei", "organization_type", "location", "region",
    "sector", "near_term_status", "near_term_target_classification", "near_term_target_year",
    "long_term_status", "long_term_target_classification", "long_term_target_year",
    "net_zero_status", "net_zero_year", "full_target_language", "ba15_status", "ba15_date",
    "target_classification_long", "status_reason", "date_updated",
]  # fmt: skip

TARGET_COLUMNS = [
    "row_entry_id", "sbti_id", "company_name", "isin", "lei", "location", "region", "sector",
    "organization_type", "validation_route", "action", "commitment_type", "commitment_deadline",
    "status", "status_reason", "full_target_language", "company_temperature_alignment",
    "target", "target_wording", "scope", "target_value", "type", "sub_type",
    "target_classification_short", "base_year", "target_year", "year_type", "date_published",
]  # fmt: skip

SBTI_ID_PATTERN = r"^4\d{7}$"

# Excel serial dates count days from this origin (Excel 1900 date system).
EXCEL_EPOCH = "1899-12-30"

# Status values as they appear in the source.
VALIDATED = "Validated Targets"
COMMITMENT = "Commitment to Set Targets"
REMOVED = "Commitment Removed"
NEAR_TERM_STATUSES = [VALIDATED, COMMITMENT, REMOVED]
NOT_RECORDED = "Not recorded"

STATUS_LABELS = {
    VALIDATED: "Validated targets",
    COMMITMENT: "Commitment to set targets",
    REMOVED: "Commitment removed",
}

# Minimum number of registered companies in a group before its percentages are compared.
DEFAULT_MIN_N = 30
TOP_N_DEFAULT = 10

# Colours, sampled from the terminal-style design reference (black surfaces, orange primary,
# cyan and coral accents). The page theme is in .streamlit/config.toml.
COLOR_ORANGE = "#F6A212"
COLOR_CYAN = "#36C6EA"
COLOR_CORAL = "#EB6460"
COLOR_VIOLET = "#B28CFF"
COLOR_GREEN = "#7DDB7D"

COLOR_BG = "#000000"
COLOR_PANEL = "#080808"
COLOR_TEXT = "#FCFCFC"
COLOR_MUTED = "#9C9C9C"
COLOR_GRID = "#2A2A2A"
COLOR_BORDER = "#4A4A4A"

# Meaning of colours: near-term validated is orange in every chart and card, and net-zero
# validated has its own colour, so a colour is never shared by two different statuses.
COLOR_VALIDATED = COLOR_ORANGE
COLOR_COMMITMENT = COLOR_CYAN
COLOR_REMOVED = COLOR_CORAL
COLOR_NET_ZERO = COLOR_VIOLET
COLOR_BAR = COLOR_ORANGE

STATUS_COLORS = {
    VALIDATED: COLOR_VALIDATED,
    COMMITMENT: COLOR_COMMITMENT,
    REMOVED: COLOR_REMOVED,
}

PROJECT_BYLINE = "Virginia Mateo Personal Project"

RESEARCH_QUESTION = (
    "How do corporate climate targets and commitments vary across sectors and countries "
    "within the SBTi register?"
)
