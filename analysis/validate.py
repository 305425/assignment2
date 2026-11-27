from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .load import Source


@dataclass
class Check:
    name: str
    expected: str
    actual: str
    status: str  # "Pass", "Fail", or "Known issue"
    note: str = ""


class ValidationError(RuntimeError):
    pass


KEY = ["Vessel_ID", "Period", "Cost_Category"]


def run_checks(src: Source) -> list[Check]:
    v, m, t, h = src.vessels, src.monthly, src.transactions, src.handover
    checks: list[Check] = []

    def add(name, expected, actual, ok, note="", known=False):
        status = "Pass" if ok else ("Known issue" if known else "Fail")
        checks.append(Check(name, expected, str(actual), status, note))

    master_ids = set(v["Vessel_ID"])
    add("Vessel IDs are unique in Vessel_Master", "14 unique", v["Vessel_ID"].nunique(),
        v["Vessel_ID"].is_unique and len(v) == 14)
    add("Monthly vessel IDs exist in Vessel_Master", "0 unmatched",
        len(set(m["Vessel_ID"]) - master_ids), set(m["Vessel_ID"]) <= master_ids)
    add("Transaction vessel IDs exist in Vessel_Master", "0 unmatched",
        len(set(t["Vessel_ID"]) - master_ids), set(t["Vessel_ID"]) <= master_ids)
    add("Handover vessel IDs exist in Vessel_Master", "0 unmatched",
        len(set(h["Vessel_ID"]) - master_ids), set(h["Vessel_ID"]) <= master_ids)

    name_map = v.set_index("Vessel_ID")["Vessel_Name"]
    name_bad = int((m["Vessel_Name"] != m["Vessel_ID"].map(name_map)).sum())
    add("Monthly vessel names match Vessel_Master", "0 mismatches", name_bad, name_bad == 0)

    periods = pd.date_range(config.FIRST_PERIOD, config.LAST_PERIOD, freq="MS")
    expected_rows = len(master_ids) * len(periods) * len(config.CATEGORIES)
    dup = int(m.duplicated(KEY).sum())
    add("Monthly key (vessel, month, category) is unique", "0 duplicates", dup, dup == 0)
    add("Monthly grid is complete", f"{expected_rows:,} rows", f"{len(m):,} rows",
        len(m) == expected_rows and set(m["Cost_Category"]) == set(config.CATEGORIES)
        and set(m["Period"]) == set(periods))

    var_diff = (m["Actual_USD"] - m["Budget_USD"] - m["Variance_USD"]).abs().max()
    add("Variance_USD equals Actual_USD minus Budget_USD",
        f"max difference <= ${config.VARIANCE_TOLERANCE_USD}", f"${var_diff:.4f}",
        var_diff <= config.VARIANCE_TOLERANCE_USD)

    pct = (m["Actual_USD"] - m["Budget_USD"]) / m["Budget_USD"]
    pct_diff = (pct - m["Variance_Pct"]).abs().max()
    add("Variance_Pct equals variance divided by budget", "max difference <= 1e-6",
        f"{pct_diff:.2e}", pct_diff <= 1e-6)
    add("Budget_USD is positive on every row", "0 rows <= 0", int((m["Budget_USD"] <= 0).sum()),
        (m["Budget_USD"] > 0).all())
    add("Transaction amounts are positive", "0 rows <= 0", int((t["Amount_USD"] <= 0).sum()),
        (t["Amount_USD"] > 0).all())
    add("Transaction IDs are unique", "0 duplicates", int(t["Transaction_ID"].duplicated().sum()),
        t["Transaction_ID"].is_unique)

    roll = t.groupby(KEY)["Amount_USD"].sum()
    joined = m.set_index(KEY)["Actual_USD"].to_frame().join(roll, how="outer")
    unmatched = int(joined.isna().any(axis=1).sum())
    diff = (joined["Actual_USD"] - joined["Amount_USD"]).abs()
    cent_cells = int((diff > 0.005).sum())
    add("Transactions roll up to monthly actual",
        f"every cell matched; max difference <= ${config.TXN_ROLLUP_TOLERANCE_USD}",
        f"{unmatched} unmatched cells; max ${diff.max():.2f}; {cent_cells:,} cells differ by cents",
        unmatched == 0 and diff.max() <= config.TXN_ROLLUP_TOLERANCE_USD + 1e-9,
        "Cent-level rounding only; net difference "
        f"${(joined['Amount_USD'] - joined['Actual_USD']).sum():.2f}.")

    nb = t[t["Budget_Status"] == "Non-Budgeted"].groupby(KEY)["Amount_USD"].sum()
    ob = m.set_index(KEY)["Off_Budget_USD"]
    both = ob.to_frame().join(nb, how="left").fillna(0.0)
    same_cells = bool(((both["Off_Budget_USD"] > 0) == (both["Amount_USD"] > 0)).all())
    equal_cells = int(np.isclose(both["Off_Budget_USD"], both["Amount_USD"], atol=1).sum()
                      - ((both["Off_Budget_USD"] == 0) & (both["Amount_USD"] == 0)).sum())
    add("Off_Budget_USD equals non-budgeted transaction spend",
        f"${nb.sum():,.2f} in {len(nb)} cells",
        f"${ob.sum():,.2f}; same {int((ob > 0).sum())} cells: {same_cells}; "
        f"amounts equal in {equal_cells} cell(s)",
        False,
        "Fields flag the same cells but disagree on amount. Off_Budget_USD is not used as "
        "unbudgeted spend; Budget_Status is used instead.",
        known=True)

    bad_counts = h[h["Overdue_Issues"] > h["Open_Issues"]]
    add("Overdue issues do not exceed open issues", "0 vessels", len(bad_counts),
        len(bad_counts) == 0,
        "Inconsistent: " + ", ".join(
            f"{r.Vessel_Name} (open {r.Open_Issues}, overdue {r.Overdue_Issues})"
            for r in bad_counts.itertuples()) if len(bad_counts) else "",
        known=True)

    missing = sorted(master_ids - set(h["Vessel_ID"]))
    add("Every vessel has a handover record", "14 of 14", f"{len(set(h['Vessel_ID']))} of 14",
        not missing,
        "No record: " + ", ".join(name_map[i] for i in missing) + ". Treated as unknown, not zero.",
        known=True)

    return checks


def assert_valid(checks: list[Check]) -> None:
    failed = [c for c in checks if c.status == "Fail"]
    if failed:
        lines = "\n".join(f"- {c.name}: expected {c.expected}, got {c.actual}" for c in failed)
        raise ValidationError(f"{len(failed)} source check(s) failed:\n{lines}")


def checks_frame(checks: list[Check]) -> pd.DataFrame:
    return pd.DataFrame([c.__dict__ for c in checks]).rename(columns={
        "name": "Check", "expected": "Expected", "actual": "Actual",
        "status": "Status", "note": "Note"})
