# Racial Equity in U.S. Grantmaking

A data pipeline and analysis of racial equity funding trends in the United States, built on IRS 990-PF e-file data and the ProPublica Nonprofit Explorer API. (Candid's Demographics and Premier APIs are scaffolded in `src/api_client.py` for future enrichment, pending an API key.)

> Companion to the *pew-racial-attitudes* project: this one analyzes how **funders** behave; that one analyzes what the **public** thinks.

## Research Question

**How has funding for racial equity changed over time, and what patterns exist in who gives, who receives, and where the money flows?**

Sub-questions:
- How did racial equity grantmaking shift before and after 2020 (George Floyd / racial justice uprisings)?
- Which funders are the largest contributors?
- What types of organizations receive racial equity funding?
- Is funding concentrated in certain regions or issue areas?

## Key Findings

*From a working sample of 990-PF returns pulled from two IRS release archives (2020 + 2023), spanning fiscal years ~2018–2022: ~57,000 grants, of which ~360 were flagged as racial-equity-related across 30 funders. This is a **convenience sample** (first N filings per archive), so the numbers below illustrate the analysis, not representative national totals.*

- **Racial equity is a small, concentrated slice.** Racial-equity-tagged grants are a low single-digit share of all foundation grants in the sample, and the dollars are highly concentrated — a few mission-aligned funders (e.g., The California Endowment) account for the large majority (high Herfindahl-Hirschman Index).
- **Recipients cluster geographically**, tracking where large racial-equity funders are based.
- **Issue mix leads with health, immigration, and civil/voting rights**, inferred from grant-purpose text (990-PF filings carry no recipient EIN, so NTEE codes require the Candid integration).
- **Time dimension is wired up but not representative.** The data spans 2018–2022 and a pre/post-2020 Welch's t-test runs, but in this convenience sample annual totals are dominated by which large funders happen to appear — so the test is a methodology demonstration. [Candid's representative research](https://blog.candid.org/post/what-does-candids-grants-data-say-about-funding-for-racial-equity-in-the-united-states/) shows racial-equity funding *rose* after 2020; confirming that here would require random sampling across many release archives.

## Methodology

1. **Data collection** — IRS 990-PF grant detail is parsed from the bulk e-file XML archives at `apps.irs.gov` (one ~400 MB ZIP chunk per run, cached locally; the IRS deprecated its AWS S3 bucket in Dec 2021). The archives mix 990/990-EZ/990-PF, so returns are filtered to 990-PF, and each filing's Part XV grant schedule is parsed for recipient, amount, and purpose. A few funders are enriched via the ProPublica Nonprofit Explorer API. *990-PF grant records contain no recipient EIN*, so recipients are keyed by name + state.
2. **Racial equity classification** — Grants are flagged as racial-equity-related if the `grant_purpose` text matches a keyword regex based on [Candid/PRE terminology](https://blog.candid.org/post/what-counts-as-racial-equity-funding/). Keywords are defined in `src/data_cleaning.py`.
3. **Storage** — Cleaned data is loaded into a local SQLite database (schema in `sql/create_tables.sql`): `foundations`, `grants`, `recipients`, `demographics`.
4. **Analysis** — Summary stats, funder concentration (HHI), geographic and issue-area breakdowns, and grant-size distribution in `notebooks/03_exploratory_analysis.ipynb`. A pre/post-2020 Welch's t-test is included and activates automatically once the loaded data spans years on both sides of 2020.

## Repository Structure

```
racial-equity-grantmaking/
├── notebooks/
│   ├── 01_data_collection.ipynb    # API calls, XML parsing, raw data assembly
│   ├── 02_data_cleaning.ipynb      # Cleaning, normalization, SQLite loading
│   ├── 03_exploratory_analysis.ipynb  # EDA, visualizations, statistical tests
│   └── 04_findings.ipynb           # Narrative findings notebook
├── src/
│   ├── api_client.py               # ProPublica, IRS 990-PF, and Candid API clients
│   ├── data_cleaning.py            # Cleaning functions, racial equity keyword tagger
│   └── visualization.py            # Chart helpers (matplotlib + plotly)
├── sql/
│   ├── create_tables.sql           # SQLite schema (foundations, grants, recipients, demographics)
│   └── analysis_queries.sql        # Standalone analysis queries
├── data/
│   └── processed/                  # Cleaned CSVs and exported figures
└── requirements.txt
```

## How to Reproduce

**Requirements:** Python 3.11+ (from [python.org](https://www.python.org/downloads/)), Git

```bash
# 1. Clone the repo
git clone https://github.com/Xanderr1/racial-equity-grantmaking.git
cd racial-equity-grantmaking

# 2. Create and activate a virtual environment
python -m venv .venv

# Mac/Linux:
source .venv/bin/activate

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# 3. Install all dependencies (includes Jupyter, ipykernel, pandas, etc.)
pip install -r requirements.txt

# 4. (Optional) Add Candid API key — needed only for demographic enrichment
#    Create a file called .env in the project root:
#    CANDID_API_KEY=your_key_here

# 5. Launch JupyterLab
jupyter lab
```

Open notebooks in order: `01` → `02` → `03` → `04`.

**Using VS Code instead of JupyterLab?**
Install the [Jupyter extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter), open the project folder, and select the `.venv` interpreter as your kernel (top-right of any notebook). All dependencies including `ipykernel` are included in `requirements.txt`.

### Windows notes

- **Use a short install path** (e.g. `C:\Projects\`). Windows has a 260-character path limit by default, and some dependencies (JupyterLab extensions) have deeply nested filenames that can overflow it. Cloning into a long path such as a synced OneDrive Documents folder may cause `pip install` to fail with `OSError: [Errno 2] No such file or directory`.
- **Install Python from [python.org](https://www.python.org/downloads/)**, not the Microsoft Store. The Store version of Python can hang when creating virtual environments (`python -m venv`).

## Data Sources

| Source | Auth | Coverage |
|---|---|---|
| [IRS 990-PF index CSVs](https://apps.irs.gov/pub/epostcard/990/xml/) | None | All e-filed 990-PFs, 2017–present (index); bulk XML ZIPs available |
| [ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/api) | None | Org profiles, NTEE codes, financials |
| [Candid Demographics API](https://developer.candid.org/) | API key (trial) | Leadership/board demographics |
| [Candid Premier API](https://developer.candid.org/) | API key (trial) | Curated grants database |

## Tested environment

Built and verified on Windows with Python 3.14; all four notebooks run end-to-end via
`jupyter nbconvert` and are committed **with their outputs** so results are visible here without
running. The IRS bulk ZIP (~400 MB) is cached after first download; raw/processed data and the
SQLite database are gitignored (reproducible by running the notebooks).

## References

- Candid. ["What does Candid's grants data say about funding for racial equity?"](https://blog.candid.org/post/what-does-candids-grants-data-say-about-funding-for-racial-equity-in-the-united-states/)
- Candid. ["What counts as racial equity funding?"](https://blog.candid.org/post/what-counts-as-racial-equity-funding/)
- Philanthropic Initiative for Racial Equity (PRE): [racialequity.org](https://racialequity.org)

## Data attribution

IRS Form 990-PF e-file data is in the public domain. ProPublica Nonprofit Explorer data is used
under their API terms. This repository's code is MIT-licensed (see `LICENSE`).

---
*Built with [Claude Code](https://claude.com/claude-code) as an AI-assisted development tool.*
