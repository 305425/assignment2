import numpy as np
import pandas as pd

from . import config
from .load import Source

KEY = ["Vessel_ID", "Period", "Cost_Category"]

COLUMNS = [
    "Vessel_ID", "Vessel_Name", "Period", "Year", "Quarter", "Month_Index", "Cost_Category",
    "Is_Partial_Year",
    "Vessel_Type", "Age_Years", "DWT", "Management_Status",
    "Budget_USD", "Actual_USD", "Variance_USD", "Variance_Pct", "Off_Budget_USD_Source",
    "Txn_Count", "Budgeted_Spend_USD", "NonBudgeted_Spend_USD", "NonBudgeted_Txn_Count",
    "Urgent_Spend_USD", "Urgent_Txn_Count", "Budgeted_Gap_USD",
    "Txn_vs_Actual_Diff_USD", "OffBudget_vs_NonBudgeted_Diff_USD",
    "Has_Handover_Record", "Open_Issues", "Overdue_Issues", "Overdue_Exceeds_Open",
    "Deferred_Exposure_USD", "Handover_Risk", "Primary_Owner",
]


def _sum_where(t: pd.DataFrame, mask: pd.Series, name: str) -> pd.Series:
    return t[mask].groupby(KEY)["Amount_USD"].sum().rename(name)


def _count_where(t: pd.DataFrame, mask: pd.Series, name: str) -> pd.Series:
    return t[mask].groupby(KEY)["Amount_USD"].size().rename(name)


def build_fact(src: Source) -> pd.DataFrame:
    m, t, v, h = src.monthly, src.transactions, src.vessels, src.handover
    every = pd.Series(True, index=t.index)
    budgeted = t["Budget_Status"] == "Budgeted"
    nonbudgeted = t["Budget_Status"] == "Non-Budgeted"
    urgent = t["Urgency"] == "Urgent"

    roll = pd.concat([
        _sum_where(t, every, "Txn_Total_USD"),
        _count_where(t, every, "Txn_Count"),
        _sum_where(t, budgeted, "Budgeted_Spend_USD"),
        _sum_where(t, nonbudgeted, "NonBudgeted_Spend_USD"),
        _count_where(t, nonbudgeted, "NonBudgeted_Txn_Count"),
        _sum_where(t, urgent, "Urgent_Spend_USD"),
        _count_where(t, urgent, "Urgent_Txn_Count"),
    ], axis=1)

    fact = m.rename(columns={"Off_Budget_USD": "Off_Budget_USD_Source"}).set_index(KEY).join(roll)
    fact[roll.columns] = fact[roll.columns].fillna(0)
    for col in ["Txn_Count", "NonBudgeted_Txn_Count", "Urgent_Txn_Count"]:
        fact[col] = fact[col].astype(int)
    fact = fact.reset_index()

    # Actual is split into budgeted and non-budgeted spend. The budgeted part absorbs the
    # cent-level rounding between the ledger and the transactions, so that
    # Variance = NonBudgeted_Spend + Budgeted_Gap holds exactly on every row.
    fact["Txn_vs_Actual_Diff_USD"] = (fact["Txn_Total_USD"] - fact["Actual_USD"]).round(2)
    fact["Budgeted_Gap_USD"] = (fact["Actual_USD"] - fact["NonBudgeted_Spend_USD"]
                                - fact["Budget_USD"])
    fact["OffBudget_vs_NonBudgeted_Diff_USD"] = (
        fact["Off_Budget_USD_Source"] - fact["NonBudgeted_Spend_USD"]).round(2)

    fact["Year"] = fact["Period"].dt.year
    fact["Quarter"] = fact["Period"].dt.to_period("Q").astype(str)
    first = pd.Timestamp(config.FIRST_PERIOD)
    fact["Month_Index"] = ((fact["Period"].dt.year - first.year) * 12
                           + fact["Period"].dt.month - first.month + 1)
    fact["Is_Partial_Year"] = fact["Year"] == config.PARTIAL_YEAR

    fact = fact.merge(v[["Vessel_ID", "Vessel_Type", "Age_Years", "DWT", "Management_Status"]],
                      on="Vessel_ID", how="left")

    ho = h.drop(columns=["Vessel_Name"]).rename(columns={
        "Estimated_Deferred_Exposure_USD": "Deferred_Exposure_USD"})
    ho["Has_Handover_Record"] = True
    ho["Overdue_Exceeds_Open"] = ho["Overdue_Issues"] > ho["Open_Issues"]
    fact = fact.merge(ho, on="Vessel_ID", how="left")
    fact["Has_Handover_Record"] = fact["Has_Handover_Record"].eq(True)
    fact["Overdue_Exceeds_Open"] = fact["Overdue_Exceeds_Open"].eq(True)

    fact = fact[COLUMNS].sort_values(KEY).reset_index(drop=True)
    return fact


def fleet_totals(fact: pd.DataFrame) -> dict:
    return {
        "budget": fact["Budget_USD"].sum(),
        "actual": fact["Actual_USD"].sum(),
        "variance": fact["Variance_USD"].sum(),
        "nonbudgeted": fact["NonBudgeted_Spend_USD"].sum(),
        "budgeted_gap": fact["Budgeted_Gap_USD"].sum(),
        "off_budget_source": fact["Off_Budget_USD_Source"].sum(),
        "urgent": fact["Urgent_Spend_USD"].sum(),
    }


def assert_identity(fact: pd.DataFrame) -> None:
    gap = fact["Variance_USD"] - fact["NonBudgeted_Spend_USD"] - fact["Budgeted_Gap_USD"]
    if not np.allclose(gap, 0, atol=0.011):
        raise AssertionError("Variance does not equal non-budgeted spend plus budgeted gap.")
