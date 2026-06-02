# Racial Equity in U.S. Grantmaking

A data analysis of racial equity funding trends in the United States, using IRS 990-PF filings, the ProPublica Nonprofit Explorer API, and Candid's Demographics and grants APIs.

## Research Question

**How has funding for racial equity changed over time, and what patterns exist in who gives, who receives, and where the money flows?**

Sub-questions:
- How did racial equity grantmaking shift before and after 2020 (George Floyd / racial justice uprisings)?
- Which funders are the largest contributors?
- What types of organizations receive racial equity funding?
- Is funding concentrated in certain regions or issue areas?

## Key Findings

*From a working sample of ~2,000 private-foundation (990-PF) returns in the IRS 2020 e-file release (fiscal years ~2018–2019): 21,000+ grants, of which ~225 were flagged as racial-equity-related. Numbers are sample-specific; the pipeline scales to more release years.*

- **Racial equity is a small, concentrated slice.** Racial-equity-tagged grants are a low single-digit share of all foundation grants in the sample, and the dollars are highly concentrated — a handful of mission-aligned funders (e.g., The California Endowment) account for the large majority (high Herfindahl-Hirschman Index).
- **Recipients cluster geographically**, tracking where large racial-equity funders are based.
- **Issue mix leads with health, immigration, and civil/voting rights**, inferred from grant-purpose text (990-PF filings carry no recipient EIN, so NTEE codes require the Candid integration).

> These patterns echo [Candid's published research](https://blog.candid.org/post/what-does-candids-grants-data-say-about-funding-for-racial-equity-in-the-united-states/) that funding for racial/ethnic communities is a modest, concentrated share of U.S. giving. A genuine pre/post-2020 time series requires loading multiple IRS release years (the analysis code is in place and runs when the data spans 2020).

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

## References

- Candid. ["What does Candid's grants data say about funding for racial equity?"](https://blog.candid.org/post/what-does-candids-grants-data-say-about-funding-for-racial-equity-in-the-united-states/)
- Candid. ["What counts as racial equity funding?"](https://blog.candid.org/post/what-counts-as-racial-equity-funding/)
- Philanthropic Initiative for Racial Equity (PRE): [racialequity.org](https://racialequity.org)

---
*Built with Claude Code
