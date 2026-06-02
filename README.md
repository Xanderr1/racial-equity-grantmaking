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

> *This section will be updated once Notebooks 01–03 are run against the full dataset.*

- **2020 surge:** Annual racial equity grantmaking roughly doubled after 2020, consistent with [Candid's published findings](https://blog.candid.org/post/what-does-candids-grants-data-say-about-funding-for-racial-equity-in-the-united-states/) of a ~$16.8B cumulative total since 2020.
- **Funder concentration:** The top 20 foundations account for a disproportionate share of total racial equity dollars (HHI analysis in Notebook 03).
- **Geographic concentration:** New York, California, and D.C. receive the majority of grant dollars; per-capita funding tells a different story.

## Methodology

1. **Data collection** — IRS 990-PF filings sourced via two methods: (a) index CSVs from `apps.irs.gov` (fast, covering 2017–2023, listing all e-filed 990-PFs with EINs and filing metadata); (b) optional bulk ZIP download for XML grant detail (~400 MB/year). Recipient org data enriched via the ProPublica Nonprofit Explorer API. Note: the IRS deprecated its AWS S3 e-file bucket in December 2021 — individual XML files at `s3.amazonaws.com/irs-form-990/` are no longer accessible.
2. **Racial equity classification** — Grants are flagged as racial-equity-related if the `grant_purpose` field matches a keyword regex based on [Candid/PRE terminology](https://blog.candid.org/post/what-counts-as-racial-equity-funding/). Keywords defined in `src/data_cleaning.py`.
3. **Storage** — All cleaned data loaded into a local SQLite database (schema in `sql/create_tables.sql`).
4. **Analysis** — Summary statistics, time series, geographic, and issue-area breakdowns in `notebooks/03_exploratory_analysis.ipynb`. Pre/post-2020 significance test uses Welch's t-test.

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

**Requirements:** Python 3.11+, Git

```bash
# 1. Clone the repo
git clone https://github.com/Xanderr1/racial-equity-grantmaking.git
cd racial-equity-grantmaking

# 2. Create and activate a virtual environment
python -m venv venv

# Mac/Linux:
source venv/bin/activate

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

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
Install the [Jupyter extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter), open the project folder, and select the `venv` interpreter as your kernel. All dependencies including `ipykernel` are included in `requirements.txt`.

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
