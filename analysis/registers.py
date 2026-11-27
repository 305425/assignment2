"""Evidence register (D3) and control register (D4), built from computed tables."""
import math

import pandas as pd

from . import config


def _usd(x):
    whole = math.floor(abs(x) + 0.5)
    return f"-${whole:,}" if x < 0 else f"${whole:,}"


def _pct(x, digits=1):
    return f"{x:+.{digits}%}"


def evidence_register(tables: dict, bt: dict, fact: pd.DataFrame) -> pd.DataFrame:
    b = tables["bridge"].set_index("Period")
    sc = tables["scorecard"].set_index("Vessel_ID")
    cat = tables["category"].set_index("Cost_Category")
    hm = tables["handover"].set_index("Vessel_ID")
    alerts = bt["fleet_alerts"]
    m = bt["metrics"].set_index(["Method", "Period"])
    ff = bt["first_flags"].set_index("Vessel_ID")
    name = sc["Vessel_Name"].str.replace("Vessel-", "", regex=False)

    nb_vessels = sc[sc["NonBudgeted_Spend_USD"] > 0]
    share_nb_vessels = nb_vessels["Variance_USD"].sum() / sc["Variance_USD"].sum()
    rec = sc[sc["Has_Handover_Record"]]
    corr = rec["Deferred_Exposure_USD"].corr(rec["Variance_USD"])
    yr = lambda c, y: cat.loc[c, f"Var_Pct_{y}"]
    sel = m.loc[("Selected rule: Escalate", "2026 (Jan-Apr)")]
    base = m.loc[("Baseline: last month > 5%", "2026 (Jan-Apr)")]
    lr = m.loc[("Logistic regression", "2026 (Jan-Apr)")]
    t = fact
    urgent_share = t["Urgent_Spend_USD"].sum() / t["Actual_USD"].sum()
    missing = hm[~hm["Has_Handover_Record"]]
    missing_nb = missing["NonBudgeted_Spend_USD"].sum()
    focus_first = ", ".join(f"{name[v]} {ff.loc[v, 'First_Escalate']:%b %Y}"
                            for v in config.FOCUS_VESSELS)
    themes = tables["hotspot_themes"]

    def top_themes(vessel, category, n=3):
        g = themes[(themes["Vessel_Name"] == vessel) & (themes["Cost_Category"] == category)]
        return ", ".join(f"{r.Description_Theme} {r.Share_Of_Category_Spend:.0%}"
                         for r in g.head(n).itertuples())

    rows = [
        ("E01", "Fleet result",
         "The fleet spent more than budget over the 31 months.",
         f"Variance {_usd(b.loc['All', 'Variance_USD'])} ({_pct(b.loc['All', 'Variance_Pct'])}) "
         f"on a {_usd(b.loc['All', 'Budget_USD'])} budget.",
         "Fleet_Bridge", "Fact", "High",
         "Budget version (original or revised) is not stated."),
        ("E02", "Fleet result",
         "Fleet variance equals non-budgeted spend plus the result on budgeted lines, and budgeted "
         "lines as a whole came in under budget (an accounting identity, not a cause; see E21).",
         f"Non-budgeted {_usd(b.loc['All', 'NonBudgeted_Spend_USD'])}; budgeted lines "
         f"{_usd(b.loc['All', 'Budgeted_Gap_USD'])}; sum equals the variance.",
         "Fleet_Bridge; Fact_Monthly", "Fact", "High",
         "The identity holds by construction. It relies on the Budget_Status flag, whose "
         "definition is unconfirmed."),
        ("E03", "Concentration",
         "All non-budgeted spend sits on five vessels, which carry most of the net overrun.",
         f"{', '.join(name[nb_vessels.index])}: {_usd(nb_vessels['NonBudgeted_Spend_USD'].sum())} "
         f"non-budgeted; {share_nb_vessels:.0%} of net fleet variance.",
         "Vessel_Scorecard", "Fact", "High", ""),
        ("E04", "Trend",
         "The monthly overrun pace rose each year.",
         f"{_usd(b.loc['2024', 'Variance_Per_Month_USD'])} per month in 2024, "
         f"{_usd(b.loc['2025', 'Variance_Per_Month_USD'])} in 2025, "
         f"{_usd(b.loc['2026', 'Variance_Per_Month_USD'])} in 2026 (Jan-Jul).",
         "Fleet_Bridge", "Fact", "Medium",
         "2026 is seven months; seasonality cannot be tested with 31 months."),
        ("E05", "Early visibility",
         "The two worst vessels were already the worst in the first half of 2024 and stayed over budget.",
         f"H72 {_pct(sc.loc['V1008', 'Var_Pct_H1_2024'])} and E48 "
         f"{_pct(sc.loc['V1005', 'Var_Pct_H1_2024'])} in H1 2024; over budget in "
         f"{sc.loc['V1008', 'Months_Over_Budget']} and {sc.loc['V1005', 'Months_Over_Budget']} "
         "of 31 months.",
         "Vessel_Scorecard", "Fact", "High", ""),
        ("E06", "Trend",
         "Repairs and safety costs deteriorated after 2024.",
         f"Repairs {_pct(yr('Repairs & Maintenance', 2024))} / {_pct(yr('Repairs & Maintenance', 2025))}"
         f" / {_pct(yr('Repairs & Maintenance', 2026))}; safety {_pct(yr('Safety & Compliance', 2024))}"
         f" / {_pct(yr('Safety & Compliance', 2025))} / {_pct(yr('Safety & Compliance', 2026))} "
         "(2024 / 2025 / 2026).",
         "Category_Trend; Fleet_Alerts", "Fact", "High",
         "Why it rose is not in the data (see E20)."),
        ("E07", "Offsets",
         "Crew wages look on budget only because non-budgeted wages offset budgeted underspend.",
         f"Variance {_usd(cat.loc['Crew Wages', 'Variance_USD'])}; non-budgeted "
         f"{_usd(cat.loc['Crew Wages', 'NonBudgeted_Spend_USD'])}; budgeted lines "
         f"{_usd(cat.loc['Crew Wages', 'Budgeted_Gap_USD'])}.",
         "Category_Trend", "Fact", "High",
         "Whether the non-budgeted wages replaced budgeted wages (relief crew) is not shown."),
        ("E08", "Offsets",
         "K56's reported variance understates its unbudgeted spend.",
         f"Variance {_usd(sc.loc['V1011', 'Variance_USD'])}; non-budgeted "
         f"{_usd(sc.loc['V1011', 'NonBudgeted_Spend_USD'])}; budgeted lines "
         f"{_usd(sc.loc['V1011', 'Budgeted_Gap_USD'])}.",
         "Vessel_Scorecard", "Fact", "High", ""),
        ("E09", "Drift",
         "L96's overrun is budget drift, not unbudgeted spend.",
         f"Variance {_usd(sc.loc['V1012', 'Variance_USD'])}, no non-budgeted spend; crew wages "
         f"{_usd(tables['hotspots'].query('Vessel_ID == \"V1012\" and Cost_Category == \"Crew Wages\"')['Variance_USD'].sum())}.",
         "Vessel_Scorecard; Hotspots", "Fact", "High", ""),
        ("E10", "Data quality",
         "Off_Budget_USD does not measure the same thing as non-budgeted transactions.",
         f"{_usd(fact['Off_Budget_USD_Source'].sum())} against "
         f"{_usd(fact['NonBudgeted_Spend_USD'].sum())}; same 228 cells, amounts equal in one.",
         "Reconciliation", "Fact", "High",
         "What Off_Budget_USD is meant to measure is an open question for the data owner."),
        ("E11", "Handover",
         "The Handover_Risk label does not follow deferred exposure or cost control.",
         f"Correlation of deferred exposure with variance {corr:+.2f}; K56 labelled "
         f"{hm.loc['V1011', 'Handover_Risk']} with the most non-budgeted spend; D49 labelled "
         f"{hm.loc['V1004', 'Handover_Risk']} with {_usd(hm.loc['V1004', 'Deferred_Exposure_USD'])} deferred.",
         "Handover_Matrix", "Fact", "Medium",
         "Scoring rule for the label is not supplied; ten vessels only."),
        ("E12", "Handover",
         "Four vessels have no handover record, including two with unbudgeted spend.",
         f"{', '.join(name[missing.index])}; {_usd(missing_nb)} non-budgeted spend on B78 and M75.",
         "Handover_Matrix; Reconciliation", "Fact", "High",
         "Missing rows are treated as unknown, not as zero risk."),
        ("E13", "Data quality",
         "K56's issue counts contradict each other.",
         f"Open {int(hm.loc['V1011', 'Open_Issues'])}, overdue {int(hm.loc['V1011', 'Overdue_Issues'])}.",
         "Reconciliation", "Fact", "High",
         "Assumes overdue issues are a subset of open issues."),
        ("E14", "Handover",
         "Recorded deferred exposure is unvalidated and is reported separately from cost performance.",
         f"{_usd(rec['Deferred_Exposure_USD'].sum())} across ten vessels.",
         "Handover_Matrix", "Open", "Low",
         "No estimation method or as-of date; not added to, netted against or compared with the overrun (a balance of work against a 31-month cost flow)."),
        ("E15", "Drivers",
         "Hotspot spend is concentrated in a few invoice themes.",
         f"H72 safety: {top_themes('Vessel-H72', 'Safety & Compliance')}. "
         f"E48 crew travel: {top_themes('Vessel-E48', 'Crew Travel', 2)}.",
         "Hotspot_Themes", "Interpretation", "Medium",
         "Themes describe what was bought, not why it was needed."),
        ("E16", "Early warning",
         "On 2026 months not used to choose the rule, the selected rule scored higher than the baselines, but the gap is within sampling noise.",
         f"Precision {sel['Precision']:.0%}, recall {sel['Recall']:.0%}, false alarms "
         f"{sel['False_Alarm_Rate']:.0%}; last-month baseline {base['Precision']:.0%} / "
         f"{base['Recall']:.0%}; logistic regression {lr['Precision']:.0%} / {lr['Recall']:.0%}.",
         "EW_Backtest; EW_Rule_Selection", "Interpretation", "Low",
         f"Test is {int(sel['Vessel_Months'])} vessel-months ({int(sel['True_Positive'])} of "
         f"{int(sel['Flags'])} flags right; base rate of bad outcomes 45%). Most bad months come from five "
         "persistent vessels, so the effective sample is small. A vessel-clustered bootstrap gives "
         "precision 40-100% and recall 33-86% for the rule, overlapping both baselines. "
         "Windows overlap; synthetic data."),
        ("E17", "Early warning",
         "The rule escalates all five unbudgeted-spend vessels in the first month it can score, so how much earlier the signal was visible cannot be tested.",
         f"First escalation: {focus_first}.",
         "EW_First_Flags", "Fact", "High",
         "June 2024 is the first month with six months of history. With three months of history the same triggers fire for B78, E48, K56 and M75 in March 2024 and H72 in April 2024."),
        ("E18", "Drivers",
         "Urgent spend is a small share of spend and almost entirely freight.",
         f"{_usd(t['Urgent_Spend_USD'].sum())} ({urgent_share:.1%} of spend); "
         f"{int(tables['urgency'].set_index('Cost_Category').loc['Logistics & Freight', 'Urgent_Txns'])}"
         f" of {int(tables['urgency']['Urgent_Txns'].sum())} urgent lines are logistics.",
         "Urgency", "Fact", "Medium", "Criteria for marking a purchase urgent are not supplied."),
        ("E19", "Drivers",
         "Vessel age, size and type do not explain the overruns in this fleet.",
         "Overruns are vessel-specific: J18 (offshore, age 20) is on budget while E48 (offshore, age 19) "
         "is the worst.",
         "Vessel_Scorecard", "Interpretation", "Low",
         "Fourteen vessels is too few to test vessel attributes statistically."),
        ("E20", "Drivers",
         "The cause of the repairs and safety deterioration cannot be determined from this data.",
         "No maintenance history, defect, dry-dock, survey schedule or purchase-order data.",
         "Evidence_and_Limitations.md", "Open", "n/a",
         "Needs planned-maintenance and defect records to explain."),
        ("E21", "Fleet result",
         "Non-budgeted spend is extra spend on top of budget, not budgeted work coded as non-budgeted.",
         "Budgeted lines are under budget by $125,727 while $711,719 is non-budgeted; crew wages shows "
         "$181,800 non-budgeted against $178,873 of budgeted underspend.",
         "Fleet_Bridge; Category_Trend", "Open", "n/a",
         "The data cannot separate extra spend from recoding or replacement of budgeted work. "
         "Needs the approvals behind the non-budgeted lines."),
    ]
    return pd.DataFrame(rows, columns=["ID", "Area", "Claim", "Figure", "Workbook_Source", "Type",
                                       "Confidence", "Caveat"])


def summary_figures(tables: dict, bt: dict, latest: pd.DataFrame) -> dict:
    """Formatted figures quoted by the management summary, so the document cannot drift."""
    b = tables["bridge"].set_index("Period")
    sc = tables["scorecard"].set_index("Vessel_ID")
    cat = tables["category"].set_index("Cost_Category")
    hm = tables["handover"]
    m = bt["metrics"].set_index(["Method", "Period"])
    short = lambda vid: sc.loc[vid, "Vessel_Name"].replace("Vessel-", "")
    nb = sc[sc["NonBudgeted_Spend_USD"] > 0]
    sel = m.loc[("Selected rule: Escalate", "2026 (Jan-Apr)")]
    base = m.loc[("Baseline: last month > 5%", "2026 (Jan-Apr)")]
    lr = m.loc[("Logistic regression", "2026 (Jan-Apr)")]
    rec = hm[hm["Has_Handover_Record"]]
    groups = []
    for decision, g in hm.groupby("Decision", sort=False):
        groups.append({
            "decision": decision,
            "vessels": ", ".join(
                short(v) + (" (Handover Review)" if s == "Handover Review" else "")
                for v, s in zip(g["Vessel_ID"], g["Management_Status"])),
        })
    return {
        "budget": _usd(b.loc["All", "Budget_USD"]),
        "actual": _usd(b.loc["All", "Actual_USD"]),
        "variance": _usd(b.loc["All", "Variance_USD"]),
        "variance_pct": _pct(b.loc["All", "Variance_Pct"]),
        "nonbudgeted": _usd(b.loc["All", "NonBudgeted_Spend_USD"]),
        "budgeted_gap": _usd(b.loc["All", "Budgeted_Gap_USD"]),
        "pace": {y: _usd(b.loc[y, "Variance_Per_Month_USD"]) for y in ["2024", "2025", "2026"]},
        "pct_by_year": {y: _pct(b.loc[y, "Variance_Pct"]) for y in ["2024", "2025", "2026"]},
        "focus_vessels": ", ".join(short(v) for v in nb.index),
        "focus_share": f"{nb['Variance_USD'].sum() / sc['Variance_USD'].sum():.0%}",
        "h72_h1": _pct(sc.loc["V1008", "Var_Pct_H1_2024"]),
        "e48_h1": _pct(sc.loc["V1005", "Var_Pct_H1_2024"]),
        "h72_months": int(sc.loc["V1008", "Months_Over_Budget"]),
        "e48_months": int(sc.loc["V1005", "Months_Over_Budget"]),
        "h72_2026": _pct(sc.loc["V1008", "Var_Pct_2026"]),
        "e48_2026": _pct(sc.loc["V1005", "Var_Pct_2026"]),
        "repairs": [_pct(cat.loc["Repairs & Maintenance", f"Var_Pct_{y}"]) for y in (2024, 2025, 2026)],
        "safety": [_pct(cat.loc["Safety & Compliance", f"Var_Pct_{y}"]) for y in (2024, 2025, 2026)],
        "wages_var": _usd(cat.loc["Crew Wages", "Variance_USD"]),
        "wages_nb": _usd(cat.loc["Crew Wages", "NonBudgeted_Spend_USD"]),
        "wages_gap": _usd(cat.loc["Crew Wages", "Budgeted_Gap_USD"]),
        "k56_var": _usd(sc.loc["V1011", "Variance_USD"]),
        "k56_nb": _usd(sc.loc["V1011", "NonBudgeted_Spend_USD"]),
        "k56_gap": _usd(sc.loc["V1011", "Budgeted_Gap_USD"]),
        "deferred": _usd(rec["Deferred_Exposure_USD"].sum()),
        "missing_records": ", ".join(short(v) for v in hm.loc[~hm["Has_Handover_Record"], "Vessel_ID"]),
        "ew": {k: f"{v:.0%}" for k, v in [("precision", sel["Precision"]), ("recall", sel["Recall"]),
                                          ("false_alarms", sel["False_Alarm_Rate"]),
                                          ("base_precision", base["Precision"]),
                                          ("base_recall", base["Recall"]),
                                          ("lr_precision", lr["Precision"]),
                                          ("lr_recall", lr["Recall"])]},
        "ew_test_rows": int(sel["Vessel_Months"]),
        "latest_escalate": ", ".join(latest.loc[latest["Level"] == "Escalate", "Vessel_Name"]
                                     .str.replace("Vessel-", "", regex=False)),
        "latest_period": f"{latest['Period'].iloc[0]:%B %Y}",
        "handover_groups": groups,
    }


def to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    lines = ["| " + " | ".join(c.replace("_", " ") for c in columns) + " |",
             "|" + "---|" * len(columns)]
    for r in df[columns].itertuples(index=False):
        lines.append("| " + " | ".join(str(v) if v else "—" for v in r) + " |")
    return "\n".join(lines)


def control_register() -> pd.DataFrame:
    rows = [
        ("C01", "New control", "Report non-budgeted spend beside variance in the monthly vessel pack.",
         "Any non-budgeted line; escalate above $10,000 in three months.", "Monthly",
         "Fleet finance", "E02, E03, E08", "Existing: Budget_Status"),
        ("C02", "New control",
         "Require approval before a non-budgeted purchase is committed, with a reason code.",
         "Every non-budgeted purchase order.", "Per purchase", "Procurement", "E02, E07",
         "New: approval record and reason code per transaction"),
        ("C03", "New control",
         "Run the early-warning rule at each month-end; an Escalate needs a written explanation "
         "from the vessel manager, and two consecutive Escalates go to management review.",
         "3-month variance above 5% or non-budgeted spend above $10,000 in three months.",
         "Monthly", "Operations", "E05, E16, E17", "Existing"),
        ("C04", "Monitor",
         "Track fleet repairs and safety variance rates against the prior-year rate.",
         "Quarterly rate above the prior-year rate.", "Quarterly", "Technical", "E06",
         "Existing"),
        ("C05", "Change",
         "Show categories where non-budgeted spend is offset by budgeted underspend, so a flat "
         "category is not read as controlled.",
         "Non-budgeted spend above 1% of category budget while net variance is near zero.",
         "Quarterly", "Fleet finance", "E07, E08", "Existing"),
        ("C06", "Change",
         "Make handover sign-off two separate decisions: cost run-rate and deferred exposure. "
         "Every managed vessel must have a handover record.",
         "Before any handover or takeover.", "Per handover", "Marine", "E11, E12, E14",
         "Existing, plus records for B78, G17, L96, M75"),
        ("C07", "Change",
         "Define Off_Budget_USD or retire it; until then report Budget_Status only.",
         "One-off.", "Once", "Fleet finance", "E10", "Definition from data owner"),
        ("C08", "Change",
         "Validate the handover register: overdue issues cannot exceed open issues; every "
         "exposure estimate carries a method and an as-of date; the risk label has a written rule.",
         "On each register update.", "Per update", "Technical", "E11, E13, E14",
         "New: issue due dates, estimate method, assessment date"),
        ("C09", "Continue",
         "Keep the budgeted-line discipline seen on A17, F86 and G17; use them as the reference "
         "for budget-setting. Review F86's deferred work before handover.",
         "n/a", "Annual budget cycle", "Technical", "E02, E11", "Existing"),
        ("C10", "Monitor",
         "Line-by-line review of the hotspots until each is under budget for three consecutive "
         "months: H72 safety, E48 crew travel, K56 and B78 repairs and spares.",
         "Hotspot category over budget in the month.", "Monthly", "Operations", "E05, E15",
         "Existing"),
        ("C11", "Before next vessel",
         "Take on a new vessel only with an opening deferred-work register (method and date), "
         "an agreed non-budgeted approval route, and a three-month baseline review.",
         "Takeover; month 3 after takeover.", "Per takeover", "Marine", "E05, E12, E14",
         "New: opening condition survey"),
        ("C12", "Data to add",
         "Link cost lines to planned-maintenance jobs, defects and purchase orders so cost "
         "movements can be explained, not only measured.",
         "n/a", "Project", "Technical", "E20",
         "New: PMS, defect list, purchase orders, crew change log"),
    ]
    return pd.DataFrame(rows, columns=["ID", "Decision_Type", "Control", "Trigger", "Frequency",
                                       "Owner_Function", "Evidence", "Data_Needed"])


def assumptions() -> pd.DataFrame:
    rows = [
        ("Unbudgeted spend", "Budget_Status = Non-Budgeted on transactions",
         "Off_Budget_USD does not reconcile to any transaction measure (E10)."),
        ("Budgeted lines vs budget", "Actual - non-budgeted spend - budget",
         "Absorbs cent-level rounding so the identity holds exactly on every row."),
        ("Fleet and vessel percentages", "Total variance / total budget",
         "Averaging row percentages would over-weight small budget lines."),
        ("Partial year", "2026 compared on rates and monthly pace",
         "2026 has seven months (Jan-Jul)."),
        ("Missing handover rows", "Unknown, not zero", "Scope of the register is not stated."),
        ("Overdue vs open issues", "Overdue assumed to be a subset of open",
         "K56 breaks this rule and is flagged (E13)."),
        ("Deferred exposure", "Reported as recorded; never added to or netted against cost",
         "No method or as-of date."),
        ("Cost band: Poor", f"Any non-budgeted spend, or variance >= {config.COST_BAND_POOR_PCT:.0%}",
         "Non-budgeted spend is a control failure regardless of net variance."),
        ("Cost band: Watch", f"Variance >= {config.COST_BAND_WATCH_PCT:.0%}",
         "Budget drift without unbudgeted spend."),
        ("Deferred exposure: material",
         f">= ${config.DEFERRED_MATERIAL_USD:,} or at least 4 overdue issues",
         "Splits the ten recorded vessels at a natural gap in the values."),
        ("Early warning: history", f"{config.EW_MIN_HISTORY_MONTHS} months before scoring",
         "Needed for the six-month features; first scored month is June 2024."),
        ("Early warning: Escalate",
         f"3-month variance > {config.EW_ESCALATE_VAR3_PCT:.0%} or non-budgeted spend > "
         f"${config.EW_NONBUDGET_ESCALATE_USD:,} in 3 months",
         "Chosen on June 2024 to September 2025; 2026 held out."),
        ("Early warning: Watch",
         f"3-month variance > {config.EW_WATCH_VAR3_PCT:.0%}, any non-budgeted spend, or a "
         f"category over {config.EW_CATEGORY_HOT_PCT:.0%} in {config.EW_CATEGORY_HOT_MONTHS} of "
         f"{config.EW_CATEGORY_HOT_WINDOW} months",
         "Category trigger moved from Escalate to Watch after the tuning period."),
        ("Early warning: outcome",
         f"Next {config.EW_HORIZON_MONTHS} months: variance > {config.EW_OUTCOME_VAR_PCT:.0%} or "
         f"non-budgeted spend > ${config.EW_OUTCOME_NONBUDGET_USD:,}",
         "A variance-only outcome is reported as a sensitivity check."),
        ("Logistic regression split", "Train Jun-Sep 2024; tune Jan-Sep 2025; test Jan-Apr 2026",
         "Training outcomes stay inside 2024 so no future months leak into training."),
    ]
    return pd.DataFrame(rows, columns=["Item", "Treatment", "Reason"])
