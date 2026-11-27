import numpy as np
import pandas as pd

from . import config


def _rate(var, budget):
    return np.where(budget != 0, var / budget, np.nan)


def fleet_bridge(fact: pd.DataFrame) -> pd.DataFrame:
    g = fact.groupby("Year").agg(
        Months=("Period", "nunique"),
        Budget_USD=("Budget_USD", "sum"),
        Actual_USD=("Actual_USD", "sum"),
        NonBudgeted_Spend_USD=("NonBudgeted_Spend_USD", "sum"),
        Budgeted_Gap_USD=("Budgeted_Gap_USD", "sum"),
        Variance_USD=("Variance_USD", "sum"),
    )
    total = g.sum(numeric_only=True)
    total["Months"] = fact["Period"].nunique()
    g.loc["All"] = total
    g["Variance_Pct"] = _rate(g["Variance_USD"], g["Budget_USD"])
    g["Variance_Per_Month_USD"] = g["Variance_USD"] / g["Months"]
    g["NonBudgeted_Per_Month_USD"] = g["NonBudgeted_Spend_USD"] / g["Months"]
    g.index = g.index.astype(str)
    return g.reset_index().rename(columns={"Year": "Period"})


def vessel_monthly(fact: pd.DataFrame) -> pd.DataFrame:
    return fact.groupby(["Vessel_ID", "Period"], as_index=False).agg(
        Budget_USD=("Budget_USD", "sum"),
        Actual_USD=("Actual_USD", "sum"),
        Variance_USD=("Variance_USD", "sum"),
        NonBudgeted_Spend_USD=("NonBudgeted_Spend_USD", "sum"),
        Urgent_Spend_USD=("Urgent_Spend_USD", "sum"),
    )


def _longest_run(flags: pd.Series) -> int:
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def cost_band(var_pct: float, nonbudgeted: float) -> str:
    if nonbudgeted > 0 or var_pct >= config.COST_BAND_POOR_PCT:
        return "Poor"
    if var_pct >= config.COST_BAND_WATCH_PCT:
        return "Watch"
    return "Controlled"


def vessel_scorecard(fact: pd.DataFrame) -> pd.DataFrame:
    attrs = fact.drop_duplicates("Vessel_ID").set_index("Vessel_ID")[[
        "Vessel_Name", "Vessel_Type", "Age_Years", "DWT", "Management_Status",
        "Has_Handover_Record", "Open_Issues", "Overdue_Issues", "Overdue_Exceeds_Open",
        "Deferred_Exposure_USD", "Handover_Risk", "Primary_Owner"]]
    tot = fact.groupby("Vessel_ID").agg(
        Budget_USD=("Budget_USD", "sum"),
        Actual_USD=("Actual_USD", "sum"),
        Variance_USD=("Variance_USD", "sum"),
        NonBudgeted_Spend_USD=("NonBudgeted_Spend_USD", "sum"),
        NonBudgeted_Txn_Count=("NonBudgeted_Txn_Count", "sum"),
        Budgeted_Gap_USD=("Budgeted_Gap_USD", "sum"),
        Urgent_Spend_USD=("Urgent_Spend_USD", "sum"),
        Actual_For_Share=("Actual_USD", "sum"),
    )
    tot["Variance_Pct"] = _rate(tot["Variance_USD"], tot["Budget_USD"])
    tot["Urgent_Share"] = tot["Urgent_Spend_USD"] / tot["Actual_For_Share"]
    tot = tot.drop(columns="Actual_For_Share")

    vm = vessel_monthly(fact).sort_values(["Vessel_ID", "Period"])
    vm["Over"] = vm["Variance_USD"] > 0
    persist = vm.groupby("Vessel_ID").agg(
        Months=("Period", "size"),
        Months_Over_Budget=("Over", "sum"),
        Longest_Over_Run=("Over", _longest_run),
    )

    h1 = fact[fact["Period"] < "2024-07-01"].groupby("Vessel_ID")[["Variance_USD", "Budget_USD"]].sum()
    yearly = fact.groupby(["Vessel_ID", "Year"])[["Variance_USD", "Budget_USD"]].sum()
    yearly_pct = (yearly["Variance_USD"] / yearly["Budget_USD"]).unstack()
    yearly_pct.columns = [f"Var_Pct_{y}" for y in yearly_pct.columns]

    sc = attrs.join(tot).join(persist).join(yearly_pct)
    sc["Var_Pct_H1_2024"] = h1["Variance_USD"] / h1["Budget_USD"]
    sc["Cost_Band"] = [cost_band(p, n) for p, n in zip(sc["Variance_Pct"], sc["NonBudgeted_Spend_USD"])]
    sc["Share_Of_Fleet_Variance"] = sc["Variance_USD"] / sc["Variance_USD"].sum()
    sc = sc.sort_values("Variance_USD", ascending=False).reset_index()
    order = ["Vessel_ID", "Vessel_Name", "Vessel_Type", "Age_Years", "DWT", "Management_Status",
             "Budget_USD", "Actual_USD", "Variance_USD", "Variance_Pct", "Share_Of_Fleet_Variance",
             "NonBudgeted_Spend_USD", "NonBudgeted_Txn_Count", "Budgeted_Gap_USD",
             "Months", "Months_Over_Budget", "Longest_Over_Run",
             "Var_Pct_H1_2024", "Var_Pct_2024", "Var_Pct_2025", "Var_Pct_2026",
             "Urgent_Spend_USD", "Urgent_Share", "Cost_Band",
             "Has_Handover_Record", "Open_Issues", "Overdue_Issues", "Overdue_Exceeds_Open",
             "Deferred_Exposure_USD", "Handover_Risk", "Primary_Owner"]
    return sc[order]


def category_trend(fact: pd.DataFrame) -> pd.DataFrame:
    g = fact.groupby(["Cost_Category", "Year"])[["Budget_USD", "Variance_USD"]].sum()
    pct = (g["Variance_USD"] / g["Budget_USD"]).unstack()
    pct.columns = [f"Var_Pct_{y}" for y in pct.columns]
    tot = fact.groupby("Cost_Category").agg(
        Budget_USD=("Budget_USD", "sum"),
        Actual_USD=("Actual_USD", "sum"),
        Variance_USD=("Variance_USD", "sum"),
        NonBudgeted_Spend_USD=("NonBudgeted_Spend_USD", "sum"),
        Budgeted_Gap_USD=("Budgeted_Gap_USD", "sum"),
        Urgent_Spend_USD=("Urgent_Spend_USD", "sum"),
    )
    tot["Variance_Pct"] = tot["Variance_USD"] / tot["Budget_USD"]
    tot["Budget_Share"] = tot["Budget_USD"] / tot["Budget_USD"].sum()
    out = tot.join(pct).sort_values("Variance_USD", ascending=False).reset_index()
    return out


def category_quarterly(fact: pd.DataFrame) -> pd.DataFrame:
    g = fact.groupby(["Quarter", "Cost_Category"])[["Budget_USD", "Variance_USD"]].sum()
    g["Variance_Pct"] = g["Variance_USD"] / g["Budget_USD"]
    months = fact.groupby("Quarter")["Period"].nunique().rename("Months_In_Quarter")
    out = g["Variance_Pct"].unstack().join(months).reset_index()
    return out


def hotspots(fact: pd.DataFrame, top_over=15, top_under=10) -> pd.DataFrame:
    fact = fact.assign(Over=fact["Variance_USD"] > 0,
                       Over_10=fact["Variance_Pct"] > config.EW_CATEGORY_HOT_PCT)
    g = fact.groupby(["Vessel_ID", "Vessel_Name", "Cost_Category"]).agg(
        Budget_USD=("Budget_USD", "sum"),
        Actual_USD=("Actual_USD", "sum"),
        Variance_USD=("Variance_USD", "sum"),
        NonBudgeted_Spend_USD=("NonBudgeted_Spend_USD", "sum"),
        Budgeted_Gap_USD=("Budgeted_Gap_USD", "sum"),
        Months_Over_Budget=("Over", "sum"),
        Months_Over_10pct=("Over_10", "sum"),
        Months=("Period", "nunique"),
    ).reset_index()
    g["Variance_Pct"] = g["Variance_USD"] / g["Budget_USD"]
    over = g.nlargest(top_over, "Variance_USD").assign(Type="Overrun")
    under = g.nsmallest(top_under, "Variance_USD").assign(Type="Saving")
    out = pd.concat([over, under], ignore_index=True)
    out["Pattern"] = np.where(out["Months_Over_Budget"] >= 0.65 * out["Months"], "Repeated",
                     np.where(out["Months_Over_Budget"] <= 0.35 * out["Months"], "Repeated under",
                              "Mixed"))
    return out


def hotspot_themes(transactions: pd.DataFrame, hot: pd.DataFrame) -> pd.DataFrame:
    keys = hot[hot["Type"] == "Overrun"][["Vessel_ID", "Vessel_Name", "Cost_Category"]]
    t = transactions.merge(keys, on=["Vessel_ID", "Cost_Category"])
    g = t.pivot_table(index=["Vessel_Name", "Cost_Category", "Description_Theme"],
                      columns="Budget_Status", values="Amount_USD", aggfunc="sum",
                      fill_value=0).reset_index()
    for col in ["Budgeted", "Non-Budgeted"]:
        if col not in g:
            g[col] = 0.0
    g["Total_USD"] = g["Budgeted"] + g["Non-Budgeted"]
    g["Share_Of_Category_Spend"] = g["Total_USD"] / g.groupby(
        ["Vessel_Name", "Cost_Category"])["Total_USD"].transform("sum")
    g = g.rename(columns={"Budgeted": "Budgeted_USD", "Non-Budgeted": "NonBudgeted_USD"})
    return g.sort_values(["Vessel_Name", "Cost_Category", "Total_USD"],
                         ascending=[True, True, False]).reset_index(drop=True)


def nonbudgeted_breakdown(transactions: pd.DataFrame) -> pd.DataFrame:
    nb = transactions[transactions["Budget_Status"] == "Non-Budgeted"]
    return nb.groupby(["Vessel_ID", "Cost_Category"]).agg(
        Txn_Count=("Amount_USD", "size"), NonBudgeted_USD=("Amount_USD", "sum")
    ).reset_index()


def urgency_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    t = transactions
    g = t.groupby(["Cost_Category", "Urgency"])["Amount_USD"].agg(["size", "sum"]).unstack(fill_value=0)
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    g = g.rename(columns={"size_Normal": "Normal_Txns", "size_Urgent": "Urgent_Txns",
                          "sum_Normal": "Normal_USD", "sum_Urgent": "Urgent_USD"})
    for c in ["Normal_Txns", "Urgent_Txns", "Normal_USD", "Urgent_USD"]:
        if c not in g:
            g[c] = 0
    g["Urgent_Share_USD"] = g["Urgent_USD"] / (g["Urgent_USD"] + g["Normal_USD"])
    return g.reset_index()[["Cost_Category", "Normal_Txns", "Urgent_Txns", "Normal_USD",
                            "Urgent_USD", "Urgent_Share_USD"]]


def _handover_axis(row) -> str:
    if not row["Has_Handover_Record"]:
        return "No record"
    if row["Deferred_Exposure_USD"] >= config.DEFERRED_MATERIAL_USD or row["Overdue_Issues"] >= 4:
        return "Material"
    return "Modest"


DECISIONS = {
    ("Poor", "Material"): "Fix cost control and deferred work before accepting responsibility",
    ("Poor", "No record"): "Investigate unbudgeted spend; create a handover record",
    ("Poor", "Modest"): "Cost review before handover",
    ("Watch", "Material"): "Deferred-work decision; monitor budget drift",
    ("Watch", "No record"): "Monitor budget drift; create a handover record",
    ("Watch", "Modest"): "Monitor budget drift",
    ("Controlled", "Material"): "Deferred-work decision; cost control can continue",
    ("Controlled", "No record"): "Continue; create a handover record",
    ("Controlled", "Modest"): "Continue current control",
}


def handover_matrix(score: pd.DataFrame) -> pd.DataFrame:
    hm = score[["Vessel_ID", "Vessel_Name", "Management_Status", "Variance_USD", "Variance_Pct",
                "NonBudgeted_Spend_USD", "Var_Pct_2026", "Cost_Band", "Has_Handover_Record",
                "Open_Issues", "Overdue_Issues", "Overdue_Exceeds_Open", "Deferred_Exposure_USD",
                "Handover_Risk", "Primary_Owner"]].copy()
    hm["Handover_Axis"] = hm.apply(_handover_axis, axis=1)
    hm["Decision"] = [DECISIONS[(c, a)] for c, a in zip(hm["Cost_Band"], hm["Handover_Axis"])]
    hm["Data_Caveat"] = np.select(
        [hm["Overdue_Exceeds_Open"], ~hm["Has_Handover_Record"]],
        ["Overdue count exceeds open count; issue counts unreliable",
         "No handover record; risk unknown, not zero"], default="")
    band_order = {"Poor": 0, "Watch": 1, "Controlled": 2}
    axis_order = {"Material": 0, "No record": 1, "Modest": 2}
    hm = hm.assign(_b=hm["Cost_Band"].map(band_order), _a=hm["Handover_Axis"].map(axis_order))
    return hm.sort_values(["_b", "_a", "Variance_USD"], ascending=[True, True, False]).drop(
        columns=["_b", "_a"]).reset_index(drop=True)


def build_all(fact: pd.DataFrame, transactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    score = vessel_scorecard(fact)
    hot = hotspots(fact)
    return {
        "bridge": fleet_bridge(fact),
        "scorecard": score,
        "category": category_trend(fact),
        "category_quarterly": category_quarterly(fact),
        "hotspots": hot,
        "hotspot_themes": hotspot_themes(transactions, hot),
        "nonbudgeted": nonbudgeted_breakdown(transactions),
        "urgency": urgency_summary(transactions),
        "handover": handover_matrix(score),
    }
