"""
Chart helper functions for the racial equity grantmaking analysis.
All functions return matplotlib Figure objects so callers can save or display.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd

# Color palette — accessible, consistent across all charts
PALETTE = {
    "primary": "#2D6A4F",      # deep green
    "accent": "#74C69D",       # light green
    "highlight": "#D62828",    # red for 2020 breakpoint
    "neutral": "#6C757D",
    "sequential": "YlGn",
}

sns.set_theme(style="whitegrid", font="DejaVu Sans")


def _fmt_millions(x, _):
    """Axis formatter: $1.2B or $450M."""
    if abs(x) >= 1e9:
        return f"${x/1e9:.1f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.0f}M"
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------

def plot_funding_over_time(
    df: pd.DataFrame,
    year_col: str = "tax_year",
    amount_col: str = "grant_amount",
    breakpoint_year: int = 2020,
    title: str = "Racial Equity Grantmaking Over Time",
) -> plt.Figure:
    """
    Bar chart of total racial equity grant dollars by year with a vertical
    line marking the 2020 breakpoint.

    Args:
        df: Grants DataFrame filtered to racial equity grants.
    """
    annual = df.groupby(year_col)[amount_col].sum().reset_index()

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(
        annual[year_col],
        annual[amount_col],
        color=[
            PALETTE["highlight"] if y >= breakpoint_year else PALETTE["primary"]
            for y in annual[year_col]
        ],
        edgecolor="white",
        linewidth=0.5,
    )
    ax.axvline(breakpoint_year - 0.5, color=PALETTE["highlight"], linestyle="--", linewidth=1.5, alpha=0.7)
    ax.text(breakpoint_year - 0.4, ax.get_ylim()[1] * 0.95, "2020", color=PALETTE["highlight"], fontsize=9)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))
    ax.set_xlabel("Tax Year")
    ax.set_ylabel("Total Grants")
    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Top funders
# ---------------------------------------------------------------------------

def plot_top_funders(
    df: pd.DataFrame,
    funder_col: str = "funder_name",
    amount_col: str = "grant_amount",
    n: int = 20,
    title: str = "Top 20 Funders by Total Racial Equity Giving",
) -> plt.Figure:
    """Horizontal bar chart of top N funders."""
    top = (
        df.groupby(funder_col)[amount_col]
        .sum()
        .nlargest(n)
        .sort_values()
    )

    fig, ax = plt.subplots(figsize=(10, max(6, n * 0.4)))
    ax.barh(top.index, top.values, color=PALETTE["primary"], edgecolor="white")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))
    ax.set_xlabel("Total Grants")
    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Geographic heatmap
# ---------------------------------------------------------------------------

def plot_state_choropleth(
    df: pd.DataFrame,
    state_col: str = "recipient_state",
    amount_col: str = "grant_amount",
    title: str = "Racial Equity Grants by Recipient State",
):
    """
    Interactive choropleth using Plotly. Returns a plotly Figure.
    Falls back gracefully if plotly is not installed.
    """
    try:
        import plotly.express as px
    except ImportError:
        raise ImportError("plotly is required for choropleth maps. Run: pip install plotly")

    state_totals = df.groupby(state_col)[amount_col].sum().reset_index()
    state_totals.columns = ["state", "total_grants"]
    state_totals["total_grants_m"] = state_totals["total_grants"] / 1e6

    fig = px.choropleth(
        state_totals,
        locations="state",
        locationmode="USA-states",
        color="total_grants_m",
        color_continuous_scale="Greens",
        scope="usa",
        labels={"total_grants_m": "Grants ($M)"},
        title=title,
    )
    fig.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
    return fig


# ---------------------------------------------------------------------------
# Grant size distribution
# ---------------------------------------------------------------------------

def plot_grant_size_distribution(
    df: pd.DataFrame,
    amount_col: str = "grant_amount",
    title: str = "Distribution of Racial Equity Grant Sizes",
) -> plt.Figure:
    """Log-scale histogram of individual grant amounts."""
    import numpy as np

    fig, ax = plt.subplots(figsize=(9, 4))
    data = df[amount_col].dropna()
    data = data[data > 0]
    ax.hist(np.log10(data), bins=40, color=PALETTE["primary"], edgecolor="white", linewidth=0.4)
    ticks = [3, 4, 5, 6, 7, 8]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"${'10K' if t==4 else '1K' if t==3 else f'{10**(t-6):.0f}M' if t>=6 else f'{10**(t-3):.0f}K'}" for t in ticks])
    ax.set_xlabel("Grant Amount (log scale)")
    ax.set_ylabel("Number of Grants")
    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# NTEE category breakdown
# ---------------------------------------------------------------------------

def plot_ntee_breakdown(
    df: pd.DataFrame,
    ntee_col: str = "ntee_major",
    amount_col: str = "grant_amount",
    title: str = "Racial Equity Grants by NTEE Category",
) -> plt.Figure:
    """Horizontal bar chart of grant dollars by NTEE major category."""
    by_ntee = (
        df.groupby(ntee_col)[amount_col]
        .sum()
        .sort_values(ascending=True)
    )

    fig, ax = plt.subplots(figsize=(9, max(5, len(by_ntee) * 0.45)))
    ax.barh(by_ntee.index, by_ntee.values, color=PALETTE["accent"], edgecolor="white")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))
    ax.set_xlabel("Total Grants")
    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Pre/post 2020 comparison
# ---------------------------------------------------------------------------

def plot_pre_post_2020(
    df: pd.DataFrame,
    year_col: str = "tax_year",
    amount_col: str = "grant_amount",
    breakpoint: int = 2020,
) -> plt.Figure:
    """
    Side-by-side bars comparing annual average giving pre- vs. post-2020.
    """
    df = df.copy()
    df["period"] = df[year_col].apply(lambda y: f"Post-{breakpoint}" if y >= breakpoint else f"Pre-{breakpoint}")
    summary = df.groupby("period")[amount_col].agg(["sum", "count"]).reset_index()
    summary["avg_annual"] = summary["sum"] / summary["count"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    colors = [PALETTE["primary"], PALETTE["highlight"]]

    for ax, (metric, label) in zip(
        axes,
        [("sum", "Total Grants"), ("avg_annual", "Avg Annual Grants")],
    ):
        ax.bar(summary["period"], summary[metric], color=colors, edgecolor="white")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))
        ax.set_title(label, fontsize=11)

    fig.suptitle(f"Racial Equity Grantmaking: Pre- vs. Post-{breakpoint}", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig
