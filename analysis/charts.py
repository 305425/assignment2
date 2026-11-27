import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from . import config  # noqa: E402

NAVY = "#1F3A5F"
RED = "#B83B3B"
AMBER = "#D99A2B"
GREEN = "#3C8D5A"
GREY = "#8A8F98"
BAND_COLOURS = {"Poor": RED, "Watch": AMBER, "Controlled": GREEN}

plt.rcParams.update({
    "font.family": "Arial", "font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150,
})


def _k(x, _=None):
    return f"${x / 1000:,.0f}k"


def _pct(x, _=None):
    return f"{x:.0%}" if abs(x) >= 0.1 or x == 0 else f"{x:.1%}"


def _save(fig, name):
    config.CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CHART_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def fleet_bridge(bridge: pd.DataFrame):
    b = bridge.set_index("Period")
    years = [p for p in b.index if p != "All"]
    labels = [f"{y}\n({int(b.loc[y, 'Months'])} months)" for y in years] + ["All\n(31 months)"]
    rows = years + ["All"]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    nb = b.loc[rows, "NonBudgeted_Spend_USD"].to_numpy()
    gap = b.loc[rows, "Budgeted_Gap_USD"].to_numpy()
    var = b.loc[rows, "Variance_USD"].to_numpy()
    ax.bar(x - 0.2, nb, 0.4, color=RED, label="Non-budgeted spend")
    ax.bar(x + 0.2, gap, 0.4, color=GREY, label="Budgeted lines vs budget")
    ax.scatter(x, var, color=NAVY, zorder=3, s=40, label="Reported variance")
    for xi, v in zip(x, var):
        ax.annotate(_k(v), (xi, v), textcoords="offset points", xytext=(0, 9), ha="center",
                    color=NAVY, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xticks(x, labels)
    ax.yaxis.set_major_formatter(_k)
    ax.set_title("Reported variance is non-budgeted spend net of budgeted underspend")
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=8)
    ax.set_ylim(min(gap.min() * 1.25, 0), nb.max() * 1.25)
    return _save(fig, "01_fleet_bridge.png")


def vessel_year_heatmap(score: pd.DataFrame):
    cols = ["Var_Pct_H1_2024", "Var_Pct_2024", "Var_Pct_2025", "Var_Pct_2026"]
    s = score.set_index("Vessel_Name")[cols]
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    norm = TwoSlopeNorm(vmin=-0.05, vcenter=0, vmax=0.12)
    im = ax.imshow(s.to_numpy(), cmap="RdYlGn_r", norm=norm, aspect="auto")
    ax.set_xticks(range(len(cols)), ["H1 2024", "2024", "2025", "2026\n(Jan-Jul)"])
    ax.set_yticks(range(len(s)), s.index)
    for i in range(s.shape[0]):
        for j in range(s.shape[1]):
            v = s.iat[i, j]
            text = "0.0%" if abs(v) < 0.0005 else f"{v:+.1%}"
            ax.text(j, i, text, ha="center", va="center", fontsize=8,
                    color="white" if v > 0.07 else "black")
    ax.set_title("Variance vs budget by vessel and year")
    cb = fig.colorbar(im, ax=ax, fraction=0.04)
    cb.ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.spines[:].set_visible(False)
    return _save(fig, "02_vessel_year_heatmap.png")


def technical_quarterly(alerts: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    for cat, colour in zip(config.TECHNICAL_CATEGORIES, [NAVY, RED]):
        q = alerts[alerts["Cost_Category"] == cat]
        labels = [f"{x}*" if m < 3 else x for x, m in zip(q["Quarter"], q["Months"])]
        ax.plot(labels, q["Variance_Pct"], marker="o", color=colour, label=f"{cat}")
        ax.axhline(q["Baseline_Pct"].iloc[0], color=colour, ls="--", lw=0.8,
                   label=f"{cat}: 2024 rate {q['Baseline_Pct'].iloc[0]:.1%}")
    ax.axvspan(-0.5, 3.5, color="#EEF1F5", zorder=0)
    ax.text(1.5, ax.get_ylim()[1] * 0.92, "baseline year", ha="center", color=GREY)
    ax.yaxis.set_major_formatter(_pct)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_title("Repairs and safety ran above their 2024 rate in every full quarter since 2025")
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left", bbox_to_anchor=(0, -0.22))
    ax.tick_params(axis="x", rotation=45)
    fig.text(0.99, 0.01, "* 2026Q3 is July only", ha="right", fontsize=7, color=GREY)
    return _save(fig, "03_technical_quarterly.png")


def nonbudgeted_by_vessel(nb: pd.DataFrame, names: pd.Series):
    p = nb.pivot_table(index="Vessel_ID", columns="Cost_Category", values="NonBudgeted_USD",
                       aggfunc="sum", fill_value=0)
    p = p.loc[p.sum(axis=1).sort_values().index]
    p.index = p.index.map(names)
    cats = [c for c in config.CATEGORIES if c in p.columns]
    colours = plt.cm.tab10(np.linspace(0, 1, 10))[: len(cats)]
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    left = np.zeros(len(p))
    for cat, col in zip(cats, colours):
        ax.barh(p.index, p[cat], left=left, color=col, label=cat)
        left += p[cat].to_numpy()
    for i, total in enumerate(left):
        ax.text(total + 2000, i, _k(total), va="center", fontweight="bold")
    ax.xaxis.set_major_formatter(_k)
    ax.set_xlim(0, left.max() * 1.15)
    ax.set_title("All $712k of non-budgeted spend sits on five vessels")
    ax.legend(frameon=False, fontsize=7.5, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.12))
    return _save(fig, "04_nonbudgeted_by_vessel.png")


def focus_runrate(scored: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    for vid, colour in [("V1008", RED), ("V1005", AMBER), ("V1002", NAVY)]:
        g = scored[scored["Vessel_ID"] == vid].sort_values("Period")
        ax.plot(g["Period"], g["Var_Pct_3m"], color=colour, label=g["Vessel_Name"].iloc[0])
    ax.axhline(config.EW_ESCALATE_VAR3_PCT, color="black", ls="--", lw=0.8)
    ax.text(scored["Period"].min(), config.EW_ESCALATE_VAR3_PCT + 0.004, "Escalate above 5%",
            fontsize=8)
    ax.axhline(0, color="black", lw=0.5)
    ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.05))
    ax.yaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.set_title("Three-month variance rate for the three largest overruns")
    ax.legend(frameon=False)
    return _save(fig, "05_focus_runrate.png")


def handover_scatter(hm: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    rec = hm[hm["Has_Handover_Record"]]
    miss = hm[~hm["Has_Handover_Record"]]
    for band, colour in BAND_COLOURS.items():
        r = rec[rec["Cost_Band"] == band]
        ax.scatter(r["Variance_Pct"], r["Deferred_Exposure_USD"], color=colour, s=60,
                   label=f"{band} cost control", zorder=3)
    offsets = {"Vessel-D49": (-62, 6), "Vessel-I27": (6, 6), "Vessel-N77": (6, -12),
               "Vessel-C68": (-20, -15)}
    for r in rec.itertuples():
        ax.annotate(f"{r.Vessel_Name.replace('Vessel-', '')} ({r.Handover_Risk})",
                    (r.Variance_Pct, r.Deferred_Exposure_USD),
                    xytext=offsets.get(r.Vessel_Name, (5, 3)),
                    textcoords="offset points", fontsize=7.5)
    y_missing = 25_000
    ax.axhspan(0, 40_000, color="#F4F4F4", zorder=0)
    for r in miss.itertuples():
        ax.scatter(r.Variance_Pct, y_missing, marker="x", color=BAND_COLOURS[r.Cost_Band], s=60)
        ax.annotate(r.Vessel_Name.replace("Vessel-", ""), (r.Variance_Pct, y_missing),
                    xytext=(5, 3), textcoords="offset points", fontsize=7.5)
    ax.text(ax.get_xlim()[0], 5_000, "  no handover record (x)", fontsize=7.5, color=GREY)
    ax.axhline(config.DEFERRED_MATERIAL_USD, color=GREY, ls="--", lw=0.8)
    ax.axvline(config.COST_BAND_POOR_PCT, color=GREY, ls="--", lw=0.8)
    ax.xaxis.set_major_formatter(_pct)
    ax.yaxis.set_major_formatter(_k)
    ax.set_xlabel("Variance vs budget, Jan 2024 to Jul 2026")
    ax.set_ylabel("Recorded deferred exposure")
    ax.set_title("Cost control and deferred exposure are different problems\n"
                 "(label in brackets = source Handover_Risk)")
    ax.set_ylim(0, 200_000)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    return _save(fig, "06_handover_matrix.png")


def ew_timeline(scored: pd.DataFrame):
    s = scored[scored["History_Months"] >= config.EW_MIN_HISTORY_MONTHS]
    grid = s.pivot_table(index="Vessel_Name", columns="Period", values="Level", aggfunc="first")
    order = s.groupby("Vessel_Name")["Escalate"].sum().sort_values(ascending=False).index
    grid = grid.loc[order]
    code = grid.apply(lambda col: col.map({"None": 0.0, "Watch": 1.0, "Escalate": 2.0}))
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    cmap = ListedColormap(["#E8ECEF", AMBER, RED])
    ax.imshow(code.to_numpy(), cmap=cmap, vmin=0, vmax=2, aspect="auto")
    ax.set_yticks(range(len(grid)), grid.index)
    cols = list(grid.columns)
    ticks = [i for i, c in enumerate(cols) if c.month in (1, 7)]
    ax.set_xticks(ticks, [cols[i].strftime("%b %Y") for i in ticks])
    ax.spines[:].set_visible(False)
    ax.set_title("Early-warning level by vessel and month (June 2024 onward)")
    ax.legend(handles=[Patch(color=RED, label="Escalate"), Patch(color=AMBER, label="Watch"),
                       Patch(color="#E8ECEF", label="No flag")],
              frameon=False, loc="upper left", bbox_to_anchor=(1.01, 1))
    return _save(fig, "07_early_warning_timeline.png")


def offbudget_comparison(score: pd.DataFrame, fact: pd.DataFrame):
    g = fact.groupby("Vessel_Name")[["Off_Budget_USD_Source", "NonBudgeted_Spend_USD"]].sum()
    g = g[(g > 0).any(axis=1)].sort_values("NonBudgeted_Spend_USD")
    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    y = np.arange(len(g))
    ax.barh(y + 0.2, g["NonBudgeted_Spend_USD"], 0.4, color=RED,
            label="Non-budgeted transactions (Budget_Status)")
    ax.barh(y - 0.2, g["Off_Budget_USD_Source"], 0.4, color=GREY,
            label="Off_Budget_USD (monthly sheet)")
    ax.set_yticks(y, g.index)
    ax.xaxis.set_major_formatter(_k)
    ax.set_title("Two 'off-budget' measures flag the same 228 cells but disagree on amount")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    return _save(fig, "08_offbudget_vs_nonbudgeted.png")


def build_all(fact, tables, bt) -> list:
    names = fact.drop_duplicates("Vessel_ID").set_index("Vessel_ID")["Vessel_Name"]
    return [
        fleet_bridge(tables["bridge"]),
        vessel_year_heatmap(tables["scorecard"]),
        technical_quarterly(bt["fleet_alerts"]),
        nonbudgeted_by_vessel(tables["nonbudgeted"], names),
        focus_runrate(bt["scored"]),
        handover_scatter(tables["handover"]),
        ew_timeline(bt["scored"]),
        offbudget_comparison(tables["scorecard"], fact),
    ]
