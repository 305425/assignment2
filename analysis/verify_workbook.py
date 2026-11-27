"""Check a recalculated workbook: no formula errors, and formula results match the Python build.

Run after Excel has recalculated the file:  py -3 -m analysis.verify_workbook
"""
import sys

import numpy as np
from openpyxl import load_workbook

from . import config, findings
from .build_dataset import build_fact
from .load import load_source

ERRORS = ("#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!")


def main(path=config.OUTPUT_DIR / "GNMTC_Vessel_Cost_Analysis.xlsx") -> int:
    formulas = load_workbook(path, data_only=False)
    values = load_workbook(path, data_only=True)
    n_formulas, errors, uncached = 0, [], []
    for ws in formulas.worksheets:
        vs = values[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    n_formulas += 1
                    v = vs[c.coordinate].value
                    if v is None:
                        uncached.append(f"{ws.title}!{c.coordinate}")
                    elif isinstance(v, str) and v in ERRORS:
                        errors.append(f"{ws.title}!{c.coordinate} {v}")

    src = load_source()
    fact = build_fact(src)
    t = findings.build_all(fact, src.transactions)
    mismatches = []

    def compare(sheet, cell, expected, label, tol=0.01):
        got = values[sheet][cell].value
        if got is None or not np.isclose(float(got), float(expected), atol=tol):
            mismatches.append(f"{label}: workbook {got}, python {expected}")

    b = t["bridge"].set_index("Period")
    for row, period in zip(range(5, 9), ["2024", "2025", "2026", "All"]):
        compare("Fleet_Bridge", f"C{row}", b.loc[period, "Budget_USD"], f"Bridge budget {period}")
        compare("Fleet_Bridge", f"E{row}", b.loc[period, "NonBudgeted_Spend_USD"], f"Bridge non-budgeted {period}")
        compare("Fleet_Bridge", f"F{row}", b.loc[period, "Budgeted_Gap_USD"], f"Bridge budgeted gap {period}")
        compare("Fleet_Bridge", f"G{row}", b.loc[period, "Variance_USD"], f"Bridge variance {period}")
        compare("Fleet_Bridge", f"H{row}", b.loc[period, "Variance_Pct"], f"Bridge variance % {period}", 1e-6)
        compare("Fleet_Bridge", f"K{row}", 0, f"Bridge identity {period}")

    sc = t["scorecard"]
    for i, r in enumerate(sc.itertuples(index=False), start=5):
        compare("Vessel_Scorecard", f"I{i}", r.Variance_USD, f"{r.Vessel_Name} variance")
        compare("Vessel_Scorecard", f"L{i}", r.NonBudgeted_Spend_USD, f"{r.Vessel_Name} non-budgeted")
        compare("Vessel_Scorecard", f"N{i}", r.Var_Pct_H1_2024, f"{r.Vessel_Name} H1 2024 %", 1e-6)
        compare("Vessel_Scorecard", f"Q{i}", r.Var_Pct_2026, f"{r.Vessel_Name} 2026 %", 1e-6)
        if values["Vessel_Scorecard"][f"U{i}"].value != r.Cost_Band:
            mismatches.append(f"{r.Vessel_Name} cost band: workbook "
                              f"{values['Vessel_Scorecard'][f'U{i}'].value}, python {r.Cost_Band}")

    cat = t["category"]
    for i, r in enumerate(cat.itertuples(index=False), start=5):
        compare("Category_Trend", f"D{i}", r.Variance_USD, f"{r.Cost_Category} variance")
        compare("Category_Trend", f"K{i}", r.Var_Pct_2026, f"{r.Cost_Category} 2026 %", 1e-6)

    ws = values["Fleet_Bridge"]
    for row in range(1, ws.max_row + 1):
        if ws[f"A{row}"].value == "Fleet budget":
            for k in range(row, row + 7):
                d = ws[f"D{k}"].value
                if d is None or abs(d) > 0.01:
                    mismatches.append(f"Cross-check '{ws[f'A{k}'].value}' difference {d}")
            break

    print(f"Formulas: {n_formulas:,}; errors: {len(errors)}; without cached value: {len(uncached)}; "
          f"mismatches with Python: {len(mismatches)}")
    for line in (errors + uncached[:10] + mismatches)[:40]:
        print("  ", line)
    return 0 if not (errors or uncached or mismatches) else 1


if __name__ == "__main__":
    sys.exit(main())
