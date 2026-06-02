"""
API clients for the racial equity grantmaking analysis project.

Active:
  - ProPublica Nonprofit Explorer (no auth required)
  - IRS 990-PF XML parser (public S3 bucket, no auth required)

Stubbed (activate after Candid API key arrives):
  - Candid Demographics API
  - Candid Essentials / Premier API
"""

import os
import time
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# ProPublica Nonprofit Explorer
# ---------------------------------------------------------------------------

PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2"


def _get(url: str, params: dict = None, retries: int = 3) -> dict:
    """GET with retry/backoff. Returns parsed JSON or raises."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt < retries - 1:
                wait = 2 ** attempt
                log.warning("Request failed (%s), retrying in %ds…", exc, wait)
                time.sleep(wait)
            else:
                raise


def propublica_search(query: str, state: str = None, ntee: int = None, page: int = 0) -> dict:
    """
    Search nonprofits by name/keyword.

    Args:
        query:  Search term (org name or keyword).
        state:  Two-letter state abbreviation filter (optional).
        ntee:   NTEE major category code 1-10 (optional).
        page:   Pagination offset (25 results per page).

    Returns:
        Raw API response dict with keys: total_results, organizations.
    """
    params = {"q": query, "page": page}
    if state:
        params["state[id]"] = state
    if ntee is not None:
        params["ntee[id]"] = ntee
    return _get(f"{PROPUBLICA_BASE}/search.json", params=params)


def propublica_organization(ein: str) -> dict:
    """
    Fetch organization profile by EIN.

    Args:
        ein: EIN with or without dashes (e.g. '13-1837418' or '131837418').

    Returns:
        Raw API response dict with org details and filings list.
    """
    ein_clean = ein.replace("-", "")
    return _get(f"{PROPUBLICA_BASE}/organizations/{ein_clean}.json")


def propublica_filings(ein: str) -> list[dict]:
    """
    Return the list of 990 filings for an org.
    Each entry has: tax_prd_yr, formtype, pdf_url, updated.
    """
    data = propublica_organization(ein)
    return data.get("filings_with_data", [])


# ---------------------------------------------------------------------------
# IRS 990-PF XML Parser  (AWS S3 public bucket)
# ---------------------------------------------------------------------------

IRS_S3_BASE = "https://s3.amazonaws.com/irs-form-990"
IRS_INDEX_BASE = "https://www.irs.gov/pub/irs-soi"

# Namespace used in IRS 990 e-file XML schemas
_NS = {
    "irs": "http://www.irs.gov/efile",
}


def fetch_990_index(year: int) -> list[dict]:
    """
    Download the IRS e-file index CSV for a given year and return rows
    for 990-PF filings only.

    The IRS publishes annual index files at:
      https://www.irs.gov/pub/irs-soi/eo{YY}index.csv   (older)
      or JSON index at s3://irs-form-990/index_YYYY.json

    We use the JSON index (available 2011-present).

    Args:
        year: Four-digit filing year (e.g. 2022).

    Returns:
        List of dicts, each with keys: EIN, DLN, ObjectId, FormType,
        SubmittedOn, LastUpdated, IsElectronic, URL.
        Filtered to FormType == '990PF'.
    """
    url = f"{IRS_S3_BASE}/index_{year}.json"
    log.info("Fetching IRS index for %d…", year)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    rows = resp.json().get("Filings", [])
    pf_rows = [r for r in rows if r.get("FormType") == "990PF"]
    log.info("  Found %d 990-PF filings for %d", len(pf_rows), year)
    return pf_rows


def download_990pf_xml(object_id: str, save: bool = True) -> str:
    """
    Download a single 990-PF XML filing from S3 by its ObjectId.

    Args:
        object_id: The ObjectId from the index (e.g. '202142349349300144').
        save:      If True, write the XML to data/raw/990pf/{object_id}.xml.

    Returns:
        Raw XML string.
    """
    url = f"{IRS_S3_BASE}/{object_id}_public.xml"
    log.info("Downloading 990-PF %s…", object_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    xml_text = resp.text

    if save:
        out_dir = RAW_DATA_DIR / "990pf"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"{object_id}.xml").write_text(xml_text, encoding="utf-8")

    return xml_text


def parse_990pf_grants(xml_text: str) -> list[dict]:
    """
    Parse a 990-PF XML filing and extract grants paid to organizations.

    Targets the GrantsAndContributionsPaidGrp section, which lists:
      - recipient name
      - recipient EIN (if disclosed)
      - recipient address (city, state)
      - grant amount
      - grant purpose

    Args:
        xml_text: Raw XML string of a 990-PF filing.

    Returns:
        List of dicts with keys:
          funder_ein, funder_name, tax_year,
          recipient_name, recipient_ein, recipient_city, recipient_state,
          grant_amount, grant_purpose.
    """
    root = ET.fromstring(xml_text)

    # Helper: find text of a tag, return None if missing
    def _text(node, path):
        el = node.find(path, _NS)
        return el.text.strip() if el is not None and el.text else None

    # Funder metadata from the Return header
    funder_ein = _text(root, ".//irs:Filer/irs:EIN")
    funder_name = _text(root, ".//irs:Filer/irs:BusinessName/irs:BusinessNameLine1Txt")
    tax_year = _text(root, ".//irs:TaxYr")

    grants = []
    for grp in root.findall(".//irs:GrantsAndContributionsPaidGrp", _NS):
        recipient_name = (
            _text(grp, "irs:RecipientBusinessName/irs:BusinessNameLine1Txt")
            or _text(grp, "irs:RecipientPersonNm")
        )
        grants.append({
            "funder_ein": funder_ein,
            "funder_name": funder_name,
            "tax_year": tax_year,
            "recipient_name": recipient_name,
            "recipient_ein": _text(grp, "irs:RecipientEIN"),
            "recipient_city": _text(grp, "irs:RecipientUSAddress/irs:CityNm"),
            "recipient_state": _text(grp, "irs:RecipientUSAddress/irs:StateAbbreviationCd"),
            "grant_amount": _text(grp, "irs:Amt"),
            "grant_purpose": _text(grp, "irs:GrantOrContributionPurposeTxt"),
        })

    return grants


def parse_990pf_funder_summary(xml_text: str) -> dict:
    """
    Extract funder-level summary fields from a 990-PF XML filing.

    Returns:
        Dict with keys: ein, name, tax_year, state, total_assets,
        total_revenue, total_grants_paid.
    """
    root = ET.fromstring(xml_text)

    def _text(node, path):
        el = node.find(path, _NS)
        return el.text.strip() if el is not None and el.text else None

    return {
        "ein": _text(root, ".//irs:Filer/irs:EIN"),
        "name": _text(root, ".//irs:Filer/irs:BusinessName/irs:BusinessNameLine1Txt"),
        "tax_year": _text(root, ".//irs:TaxYr"),
        "state": _text(root, ".//irs:Filer/irs:USAddress/irs:StateAbbreviationCd"),
        "total_assets": _text(root, ".//irs:TotalAssetsEOYAmt"),
        "total_revenue": _text(root, ".//irs:TotalRevAndExpnssAmt"),
        "total_grants_paid": _text(root, ".//irs:TotalGrantsAndContriPdAmt"),
    }


# ---------------------------------------------------------------------------
# Candid Demographics API  (STUB — activate when API key is available)
# ---------------------------------------------------------------------------

CANDID_DEMOGRAPHICS_BASE = "https://api.candid.org/demographics/v1"


def candid_demographics(ein: str, api_key: str = None) -> dict:
    """
    Fetch nonprofit leadership and board demographic data from Candid.

    Args:
        ein:     EIN without dashes.
        api_key: Candid API key. Falls back to CANDID_API_KEY env var.

    Returns:
        Raw API response dict with demographic breakdowns.

    Raises:
        NotImplementedError: Until a valid API key is configured.
    """
    key = api_key or os.environ.get("CANDID_API_KEY")
    if not key:
        raise NotImplementedError(
            "Candid API key not configured. Set CANDID_API_KEY env var or pass api_key=. "
            "Trial access: https://developer.candid.org/reference/getting-access"
        )
    headers = {"Subscription-Key": key}
    return _get(f"{CANDID_DEMOGRAPHICS_BASE}/organizations/{ein}", )


# ---------------------------------------------------------------------------
# Candid Essentials / Premier API  (STUB — activate when API key is available)
# ---------------------------------------------------------------------------

CANDID_ESSENTIALS_BASE = "https://api.candid.org/premier/v1"


def candid_grants_search(
    ein: str = None,
    keyword: str = None,
    year_from: int = None,
    year_to: int = None,
    api_key: str = None,
) -> dict:
    """
    Search grants data from Candid Premier API.

    Args:
        ein:       Recipient EIN filter.
        keyword:   Grant purpose keyword filter.
        year_from: Start year filter.
        year_to:   End year filter.
        api_key:   Candid API key. Falls back to CANDID_API_KEY env var.

    Returns:
        Raw API response with grants list and pagination metadata.

    Raises:
        NotImplementedError: Until a valid API key is configured.
    """
    key = api_key or os.environ.get("CANDID_API_KEY")
    if not key:
        raise NotImplementedError(
            "Candid API key not configured. Set CANDID_API_KEY env var or pass api_key=. "
            "Trial access: https://developer.candid.org/reference/getting-access"
        )
    params = {}
    if ein:
        params["recipient_ein"] = ein
    if keyword:
        params["grant_subject"] = keyword
    if year_from:
        params["year_from"] = year_from
    if year_to:
        params["year_to"] = year_to

    headers = {"Subscription-Key": key}
    return _get(f"{CANDID_ESSENTIALS_BASE}/grants", params=params)
