"""
API clients for the racial equity grantmaking analysis project.

Active:
  - ProPublica Nonprofit Explorer (no auth required)
  - IRS 990-PF: index via apps.irs.gov CSV; XMLs via bulk ZIP download

Stubbed (activate after Candid API key arrives):
  - Candid Demographics API
  - Candid Essentials / Premier API

NOTE on IRS data: The IRS deprecated its S3 e-file bucket in Dec 2021.
Individual XML files are no longer available at direct URLs. Data is now
distributed as bulk ZIP archives at:
  https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/download990xml_{YEAR}_{chunk}.zip
Index CSVs (small, fast) are still at:
  https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/index_{YEAR}.csv
"""

import io
import os
import time
import logging
import zipfile
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
# IRS 990-PF Data  (apps.irs.gov — IRS deprecated S3 bucket in Dec 2021)
# ---------------------------------------------------------------------------

IRS_BASE = "https://apps.irs.gov/pub/epostcard/990/xml"

# Namespace used in IRS 990 e-file XML schemas
_NS = {
    "irs": "http://www.irs.gov/efile",
}

# Known chunk identifiers by year (from IRS downloads page)
_IRS_CHUNKS = {
    2020: [str(i) for i in range(1, 9)],   # 2020: chunks 1-8
    2019: [str(i) for i in range(1, 9)],
    2018: [str(i) for i in range(1, 9)],
    2017: [str(i) for i in range(1, 9)],
}


def fetch_990_index(year: int) -> list[dict]:
    """
    Download the IRS e-file index CSV for a given year and return rows
    for 990-PF filings only.

    Index CSVs are at:
      https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/index_{YEAR}.csv

    Columns: RETURN_ID, FILING_TYPE, EIN, TAX_PERIOD, SUB_DATE,
             TAXPAYER_NAME, RETURN_TYPE, DLN, OBJECT_ID

    Args:
        year: Four-digit tax year (e.g. 2020). Data available from ~2017.

    Returns:
        List of dicts with keys matching CSV columns, filtered to
        RETURN_TYPE == '990PF'.
    """
    url = f"{IRS_BASE}/{year}/index_{year}.csv"
    log.info("Fetching IRS index for %d…", year)
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()

    rows = []
    lines = resp.iter_lines()
    headers = next(lines).decode("utf-8").split(",")
    for line in lines:
        values = line.decode("utf-8").split(",")
        row = dict(zip(headers, values))
        if row.get("RETURN_TYPE") == "990PF":
            rows.append(row)

    log.info("  Found %d 990-PF filings for %d", len(rows), year)
    return rows


def download_990pf_from_zip(year: int, object_ids: list[str], chunk: str,
                             save: bool = True) -> dict[str, str]:
    """
    Download a ZIP chunk from the IRS and extract specific 990-PF XMLs by ObjectId.

    The IRS provides bulk ZIP archives at:
      https://apps.irs.gov/pub/epostcard/990/xml/{YEAR}/download990xml_{YEAR}_{chunk}.zip

    Each ZIP contains individual XML files named '{OBJECT_ID}_public.xml'.

    Args:
        year:       Four-digit tax year.
        object_ids: List of OBJECT_ID strings to extract from the ZIP.
        chunk:      Chunk identifier (e.g. '1', '2', '01A').
        save:       If True, save extracted XMLs to data/raw/990pf/.

    Returns:
        Dict mapping object_id → xml_text for successfully extracted files.
    """
    url = f"{IRS_BASE}/{year}/download990xml_{year}_{chunk}.zip"
    log.info("Downloading ZIP chunk %s for %d (~400MB, may take a while)…", chunk, year)

    resp = requests.get(url, timeout=600, stream=True)
    resp.raise_for_status()

    # Buffer the full ZIP in memory (required for random access within ZIP)
    zip_bytes = io.BytesIO()
    downloaded = 0
    for data in resp.iter_content(chunk_size=1024 * 1024):
        zip_bytes.write(data)
        downloaded += len(data)
        if downloaded % (50 * 1024 * 1024) == 0:
            log.info("  Downloaded %d MB…", downloaded // (1024 * 1024))

    zip_bytes.seek(0)
    target_names = {f"{oid}_public.xml" for oid in object_ids}
    results = {}

    with zipfile.ZipFile(zip_bytes) as zf:
        available = set(zf.namelist())
        found = available & target_names
        log.info("  Found %d/%d requested files in ZIP", len(found), len(object_ids))
        for name in found:
            oid = name.replace("_public.xml", "")
            xml_text = zf.read(name).decode("utf-8")
            results[oid] = xml_text
            if save:
                out_dir = RAW_DATA_DIR / "990pf"
                out_dir.mkdir(exist_ok=True)
                (out_dir / f"{oid}.xml").write_text(xml_text, encoding="utf-8")

    return results


def load_cached_990pf_xml(object_id: str) -> Optional[str]:
    """
    Load a previously downloaded 990-PF XML from the local cache.
    Returns None if not cached.
    """
    path = RAW_DATA_DIR / "990pf" / f"{object_id}.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _download_zip_to_cache(year: int, chunk: str) -> Path:
    """
    Download a bulk 990 ZIP chunk to data/raw/ (cached). Returns the local path.

    The IRS bundles ALL Form 990 series returns (990, 990-EZ, 990-PF) in these
    archives, so callers must filter to 990-PF after extraction.
    """
    cache = RAW_DATA_DIR / f"_chunk_{year}_{chunk}.zip"
    if cache.exists() and cache.stat().st_size > 1_000_000:
        log.info("Using cached ZIP %s", cache.name)
        return cache

    url = f"{IRS_BASE}/{year}/download990xml_{year}_{chunk}.zip"
    log.info("Downloading ZIP chunk %s for %d (~400MB, one time)…", chunk, year)
    resp = requests.get(url, timeout=600, stream=True)
    resp.raise_for_status()

    downloaded = 0
    with open(cache, "wb") as fh:
        for data in resp.iter_content(chunk_size=1024 * 1024):
            fh.write(data)
            downloaded += len(data)
            if downloaded % (50 * 1024 * 1024) == 0:
                log.info("  Downloaded %d MB…", downloaded // (1024 * 1024))
    return cache


def sample_990pf_from_zip(year: int, chunk: str = "1", max_filings: int = 400,
                          save: bool = True) -> dict[str, str]:
    """
    Download a bulk 990 ZIP chunk and return 990-PF filings from it.

    Reads the ZIP directly and filters to 990-PF returns by inspecting each
    file's ReturnTypeCd (the bulk archives mix 990, 990-EZ and 990-PF, and the
    annual index CSVs do NOT line up with the ZIP contents — so we filter here
    rather than matching ObjectIds).

    Args:
        year:        Processing year of the archive (e.g. 2020). ZIPs exist for
                     2017-2020 as numbered chunks '1'..'8', 2021+ as '01A' etc.
        chunk:       Chunk identifier within the year.
        max_filings: Stop after collecting this many 990-PF filings.
        save:        If True, cache each extracted XML under data/raw/990pf/.

    Returns:
        Dict mapping object_id → xml_text for up to `max_filings` 990-PF returns.
    """
    cache = _download_zip_to_cache(year, chunk)
    results = {}

    with zipfile.ZipFile(cache) as zf:
        for name in zf.namelist():
            if len(results) >= max_filings:
                break
            data = zf.read(name)
            # Fast pre-filter before full XML parse
            if b"ReturnTypeCd>990PF" not in data:
                continue
            oid = name.replace("_public.xml", "")
            xml_text = data.decode("utf-8", errors="replace")
            results[oid] = xml_text
            if save:
                out_dir = RAW_DATA_DIR / "990pf"
                out_dir.mkdir(exist_ok=True)
                (out_dir / f"{oid}.xml").write_text(xml_text, encoding="utf-8")

    log.info("Collected %d 990-PF filings from %d chunk %s", len(results), year, chunk)
    return results


def parse_990pf_grants(xml_text: str) -> list[dict]:
    """
    Parse a 990-PF XML filing and extract grants paid to organizations.

    Targets the GrantOrContributionPdDurYrGrp section (Form 990-PF Part XV,
    "Grants and Contributions Paid During the Year"), which lists:
      - recipient business/person name
      - recipient address (city, state)
      - grant amount
      - grant purpose

    NOTE: 990-PF grant records do NOT include the recipient's EIN — the form
    only requires name and address. recipient_ein is therefore always None;
    recipients are identified by name + state.

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
    for grp in root.findall(".//irs:GrantOrContributionPdDurYrGrp", _NS):
        recipient_name = (
            _text(grp, "irs:RecipientBusinessName/irs:BusinessNameLine1Txt")
            or _text(grp, "irs:RecipientPersonNm")
        )
        grants.append({
            "funder_ein": funder_ein,
            "funder_name": funder_name,
            "tax_year": tax_year,
            "recipient_name": recipient_name,
            "recipient_ein": None,  # not present in 990-PF grant records
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
        "total_grants_paid": _text(root, ".//irs:TotalGrantOrContriPdDurYrAmt"),
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
