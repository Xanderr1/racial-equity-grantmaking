"""
Reusable cleaning and transformation functions for the racial equity
grantmaking analysis pipeline.
"""

import re
import sqlite3
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "racial_equity_grants.sqlite"

# ---------------------------------------------------------------------------
# EIN normalization
# ---------------------------------------------------------------------------

def normalize_ein(ein) -> Optional[str]:
    """
    Normalize an EIN to 9-digit zero-padded string without dashes.
    Returns None if the input cannot be parsed as a valid EIN.
    """
    if ein is None:
        return None
    digits = re.sub(r"\D", "", str(ein))
    if len(digits) == 9:
        return digits
    if len(digits) < 9:
        # Pad leading zeros (some sources strip them)
        padded = digits.zfill(9)
        if len(padded) == 9:
            return padded
    return None


def format_ein_display(ein: str) -> Optional[str]:
    """Format a 9-digit EIN as XX-XXXXXXX for display."""
    clean = normalize_ein(ein)
    if clean:
        return f"{clean[:2]}-{clean[2:]}"
    return None


# ---------------------------------------------------------------------------
# Org name normalization
# ---------------------------------------------------------------------------

_SUFFIXES = re.compile(
    r"\b(inc\.?|incorporated|corp\.?|corporation|llc\.?|ltd\.?|foundation|fdn\.?|"
    r"assoc\.?|association|org\.?|organization)\b",
    re.IGNORECASE,
)


def normalize_org_name(name: str) -> Optional[str]:
    """
    Lowercase, strip punctuation noise, collapse whitespace.
    Does NOT remove legal suffixes — keeps them for deduplication matching.
    """
    if not name:
        return None
    name = name.upper().strip()
    # Remove non-alphanumeric except spaces and hyphens
    name = re.sub(r"[^\w\s\-]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# Grant amount cleaning
# ---------------------------------------------------------------------------

def clean_amount(value) -> Optional[float]:
    """
    Parse a grant amount to float. Handles strings like '$1,500,000' or '1500000'.
    Returns None for missing/unparseable values.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    cleaned = re.sub(r"[$,\s]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Racial equity keyword classification
# ---------------------------------------------------------------------------

# Keywords drawn from Candid / PRE methodology for racial equity funding.
# A grant is classified as racial-equity-related if its purpose text matches
# at least one term.
_RACIAL_EQUITY_KEYWORDS = [
    r"\bracial\s+equity\b",
    r"\bracial\s+justice\b",
    r"\banti[\s\-]?racism\b",
    r"\banti[\s\-]?racist\b",
    r"\bblack[\s\-]led\b",
    r"\bblack\s+community\b",
    r"\bblack\s+youth\b",
    r"\bindigenous[\s\-]led\b",
    r"\bpeople\s+of\s+color\b",
    r"\bcommunities\s+of\s+color\b",
    r"\blatino[sx]?\b",
    r"\blatinx\b",
    r"\bchicano\b",
    r"\bpoc\b",
    r"\bbipoc\b",
    r"\bsystemic\s+racism\b",
    r"\bstructural\s+racism\b",
    r"\bwhite\s+supremacy\b",
    r"\bequity\s+and\s+inclusion\b",
    r"\bdiversity,?\s+equity\b",
    r"\bminority[\s\-]led\b",
    r"\bminority\s+community\b",
    r"\bunderrepresented\s+minorit",
    r"\bcivil\s+rights\b",
    r"\bvoting\s+rights\b",
    r"\bimmigrant\s+rights\b",
    r"\brefugee\b",
    r"\bnative\s+american\b",
    r"\bamerican\s+indian\b",
    r"\baapi\b",
    r"\basian\s+american\b",
    r"\bpacific\s+islander\b",
]

_RE_RACIAL_EQUITY = re.compile(
    "|".join(_RACIAL_EQUITY_KEYWORDS), re.IGNORECASE
)


def is_racial_equity_grant(purpose_text: str) -> bool:
    """
    Return True if the grant purpose text matches racial equity keywords.
    Returns False for empty/None input.
    """
    if not purpose_text:
        return False
    return bool(_RE_RACIAL_EQUITY.search(purpose_text))


def tag_racial_equity(df: pd.DataFrame, purpose_col: str = "grant_purpose") -> pd.DataFrame:
    """
    Add a boolean 'is_racial_equity' column to a grants DataFrame.
    """
    df = df.copy()
    df["is_racial_equity"] = df[purpose_col].apply(is_racial_equity_grant)
    return df


# ---------------------------------------------------------------------------
# DataFrame cleaning entrypoints
# ---------------------------------------------------------------------------

def clean_grants_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply standard cleaning to a raw grants DataFrame.

    Expects columns: funder_ein, funder_name, tax_year, recipient_name,
    recipient_ein, recipient_city, recipient_state, grant_amount, grant_purpose.

    Returns cleaned DataFrame with normalized columns and is_racial_equity tag.
    """
    df = df.copy()

    df["funder_ein"] = df["funder_ein"].apply(normalize_ein)
    df["recipient_ein"] = df["recipient_ein"].apply(normalize_ein)
    df["funder_name"] = df["funder_name"].apply(normalize_org_name)
    df["recipient_name"] = df["recipient_name"].apply(normalize_org_name)
    df["grant_amount"] = df["grant_amount"].apply(clean_amount)
    df["tax_year"] = pd.to_numeric(df["tax_year"], errors="coerce").astype("Int64")

    # Drop rows with no funder EIN or amount
    before = len(df)
    df = df.dropna(subset=["funder_ein", "grant_amount"])
    dropped = before - len(df)
    if dropped:
        log.info("Dropped %d rows missing funder_ein or grant_amount", dropped)

    df = tag_racial_equity(df)
    return df.reset_index(drop=True)


def clean_foundations_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a foundations (funders) summary DataFrame.

    Expects columns: ein, name, tax_year, state, total_assets,
    total_revenue, total_grants_paid.
    """
    df = df.copy()
    df["ein"] = df["ein"].apply(normalize_ein)
    df["name"] = df["name"].apply(normalize_org_name)
    df["tax_year"] = pd.to_numeric(df["tax_year"], errors="coerce").astype("Int64")
    for col in ["total_assets", "total_revenue", "total_grants_paid"]:
        df[col] = df[col].apply(clean_amount)
    return df.dropna(subset=["ein"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# SQLite loader
# ---------------------------------------------------------------------------

def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def load_table(df: pd.DataFrame, table: str, conn: sqlite3.Connection, if_exists: str = "append") -> int:
    """
    Write a DataFrame to a SQLite table. Returns number of rows written.

    Args:
        df:        Cleaned DataFrame.
        table:     Target table name.
        conn:      Open SQLite connection.
        if_exists: 'append' (default) or 'replace'.
    """
    df.to_sql(table, conn, if_exists=if_exists, index=False)
    log.info("Loaded %d rows into '%s'", len(df), table)
    return len(df)
