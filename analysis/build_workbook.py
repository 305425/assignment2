from datetime import datetime

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from . import config
from .build_dataset import COLUMNS as FACT_COLUMNS

FONT = "Arial"
NAVY = "1F3A5F"
USD = '$#,##0;($#,##0);"-"'
USD_CENTS = '$#,##0.00;($#,##0.00);"-"'
PCT = '0.0%;-0.0%;"-"'
DATE = "mmm yyyy"

HEADER_FONT = Font(name=FONT, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
TITLE_FONT = Font(name=FONT, bold=True, size=14, color=NAVY)
NOTE_FONT = Font(name=FONT, italic=True, size=9, color="555555")
BODY_FONT = Font(name=FONT, size=10)
LINK_FONT = Font(name=FONT, size=10, color="008000")
INPUT_FONT = Font(name=FONT, size=10, color="0000FF")
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
BOLD_FONT = Font(name=FONT, size=10, bold=True)
TOTAL_BORDER = Border(top=Side(style="thin", color="000000"))

FACT = "Fact_Monthly"
FACT_LAST = 1 + 14 * 31 * 8


def _fact_range(column: str) -> str:
    letter = get_column_letter(FACT_COLUMNS.index(column) + 1)
    return f"{FACT}!${letter}$2:${letter}${FACT_LAST}"


R = {c: _fact_range(c) for c in FACT_COLUMNS}


def _fmt_for(col: str):
    c = col.lower()
    if c.endswith("_usd") or c in ("budgeted_usd", "nonbudgeted_usd", "total_usd"):
        return USD
    if any(k in c for k in ("pct", "share", "precision", "recall", "rate", "prob")):
        return PCT
    return None


def _title(ws: Worksheet, title: str, note: str = "") -> None:
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    if note:
        ws["A2"] = note
        ws["A2"].font = NOTE_FONT


def _header(ws: Worksheet, row: int, headers: list[str]) -> None:
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=j, value=h.replace("_", " "))
        c.font, c.fill = HEADER_FONT, HEADER_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 30


def _value(v):
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.to_pydatetime()
    if v is pd.NaT:
        return None
    return v


def write_frame(ws: Worksheet, df: pd.DataFrame, start_row: int = 4, widths: dict | None = None,
                wrap: tuple = (), freeze: bool = True, autofilter: bool = True) -> int:
    _header(ws, start_row, list(df.columns))
    fmts = {j: _fmt_for(c) for j, c in enumerate(df.columns, start=1)}
    date_cols = {j for j, c in enumerate(df.columns, start=1)
                 if pd.api.types.is_datetime64_any_dtype(df[c])}
    for i, row in enumerate(df.itertuples(index=False), start=start_row + 1):
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=i, column=j, value=_value(v))
            c.font = BODY_FONT
            if j in date_cols:
                c.number_format = DATE
            elif fmts[j]:
                c.number_format = fmts[j]
            if df.columns[j - 1] in wrap:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    for j, col in enumerate(df.columns, start=1):
        width = (widths or {}).get(col, min(max(len(col) * 0.9 + 2, 10), 22))
        ws.column_dimensions[get_column_letter(j)].width = width
    if freeze:
        ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    if autofilter and len(df):
        ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(df.columns))}{start_row + len(df)}"
    return start_row + len(df)


def _set(ws, ref, value, fmt=None, font=BODY_FONT):
    ws[ref] = value
    ws[ref].font = font
    if fmt:
        ws[ref].number_format = fmt


# ---------------------------------------------------------------- formula sheets


def sheet_bridge(wb, bridge: pd.DataFrame):
    ws = wb.create_sheet("Fleet_Bridge")
    _title(ws, "Fleet bridge: budget to actual by year",
           "All figures are SUMIFS formulas over Fact_Monthly. Variance = non-budgeted spend + "
           "budgeted lines vs budget. 2026 is January to July.")
    headers = ["Period", "Months", "Budget_USD", "Actual_USD", "NonBudgeted_Spend_USD",
               "Budgeted_Gap_USD", "Variance_USD", "Variance_Pct", "Variance_Per_Month_USD",
               "NonBudgeted_Per_Month_USD", "Identity_Check_USD"]
    _header(ws, 4, headers)
    years = [2024, 2025, 2026]
    for i, y in enumerate(years, start=5):
        _set(ws, f"A{i}", y, "0")
        _set(ws, f"B{i}", f"=COUNTIFS({R['Year']},A{i})/{14 * 8}", "0", LINK_FONT)
        for col, src in zip("CDEFG", ["Budget_USD", "Actual_USD", "NonBudgeted_Spend_USD",
                                      "Budgeted_Gap_USD", "Variance_USD"]):
            _set(ws, f"{col}{i}", f"=SUMIFS({R[src]},{R['Year']},$A{i})", USD, LINK_FONT)
    t = 5 + len(years)
    _set(ws, f"A{t}", "All", font=BOLD_FONT)
    for col in "BCDEFG":
        _set(ws, f"{col}{t}", f"=SUM({col}5:{col}{t - 1})", "0" if col == "B" else USD, BOLD_FONT)
    for i in range(5, t + 1):
        f = BOLD_FONT if i == t else BODY_FONT
        _set(ws, f"H{i}", f"=IF(C{i}=0,0,G{i}/C{i})", PCT, f)
        _set(ws, f"I{i}", f"=IF(B{i}=0,0,G{i}/B{i})", USD, f)
        _set(ws, f"J{i}", f"=IF(B{i}=0,0,E{i}/B{i})", USD, f)
        _set(ws, f"K{i}", f"=ROUND(G{i}-E{i}-F{i},2)", USD_CENTS, f)
    for col in "ABCDEFGHIJK":
        ws[f"{col}{t}"].border = TOTAL_BORDER

    c = t + 3
    _set(ws, f"A{c}", "Cross-checks against the Python build", font=BOLD_FONT)
    _header(ws, c + 1, ["Measure", "Workbook formula", "Python value", "Difference"])
    all_row = bridge.set_index("Period").loc["All"]
    checks = [
        ("Fleet budget", f"=C{t}", all_row["Budget_USD"]),
        ("Fleet actual", f"=D{t}", all_row["Actual_USD"]),
        ("Fleet variance", f"=G{t}", all_row["Variance_USD"]),
        ("Non-budgeted spend", f"=E{t}", all_row["NonBudgeted_Spend_USD"]),
        ("Budgeted lines vs budget", f"=F{t}", all_row["Budgeted_Gap_USD"]),
        ("Vessel scorecard variance total", "=SUM(Vessel_Scorecard!I5:I18)", all_row["Variance_USD"]),
        ("Category trend variance total", "=SUM(Category_Trend!D5:D12)", all_row["Variance_USD"]),
    ]
    for k, (label, formula, value) in enumerate(checks, start=c + 2):
        _set(ws, f"A{k}", label)
        _set(ws, f"B{k}", formula, USD_CENTS, LINK_FONT if "!" in formula else BODY_FONT)
        _set(ws, f"C{k}", float(value), USD_CENTS, INPUT_FONT)
        _set(ws, f"D{k}", f"=ROUND(B{k}-C{k},2)", USD_CENTS)
    _set(ws, f"A{c + 2 + len(checks)}",
         "Python values are hard-coded from analysis/findings.py; a non-zero difference means the "
         "workbook and the build disagree.", font=NOTE_FONT)
    widths = [12, 9, 15, 15, 17, 17, 15, 11, 15, 17, 14]
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.column_dimensions["A"].width = 32
    ws.freeze_panes = "A5"


def sheet_scorecard(wb, score: pd.DataFrame):
    ws = wb.create_sheet("Vessel_Scorecard")
    _title(ws, "Vessel scorecard, January 2024 to July 2026",
           "Green columns are SUMIFS formulas over Fact_Monthly; black are values from "
           "analysis/findings.py. Cost band uses the thresholds on the Assumptions sheet.")
    headers = ["Vessel_ID", "Vessel_Name", "Vessel_Type", "Age_Years", "DWT", "Management_Status",
               "Budget_USD", "Actual_USD", "Variance_USD", "Variance_Pct", "Share_Of_Fleet_Variance",
               "NonBudgeted_Spend_USD", "Budgeted_Gap_USD", "Var_Pct_H1_2024", "Var_Pct_2024",
               "Var_Pct_2025", "Var_Pct_2026", "Months_Over_Budget", "Longest_Over_Run",
               "Urgent_Share", "Cost_Band", "Has_Handover_Record", "Open_Issues", "Overdue_Issues",
               "Deferred_Exposure_USD", "Handover_Risk", "Primary_Owner"]
    _header(ws, 4, headers)
    n = len(score)
    last = 4 + n
    for i, r in enumerate(score.itertuples(index=False), start=5):
        for col, v in zip("ABCDEF", [r.Vessel_ID, r.Vessel_Name, r.Vessel_Type, r.Age_Years,
                                     r.DWT, r.Management_Status]):
            _set(ws, f"{col}{i}", _value(v), "#,##0" if col == "E" else None)
        for col, src in zip("GHI", ["Budget_USD", "Actual_USD", "Variance_USD"]):
            _set(ws, f"{col}{i}", f"=SUMIFS({R[src]},{R['Vessel_ID']},$A{i})", USD, LINK_FONT)
        _set(ws, f"J{i}", f"=IF(G{i}=0,0,I{i}/G{i})", PCT)
        _set(ws, f"K{i}", f"=I{i}/SUM($I$5:$I${last})", PCT)
        _set(ws, f"L{i}", f"=SUMIFS({R['NonBudgeted_Spend_USD']},{R['Vessel_ID']},$A{i})", USD, LINK_FONT)
        _set(ws, f"M{i}", f"=SUMIFS({R['Budgeted_Gap_USD']},{R['Vessel_ID']},$A{i})", USD, LINK_FONT)
        h1 = f'{R["Period"]},"<"&DATE(2024,7,1)'
        _set(ws, f"N{i}",
             f"=SUMIFS({R['Variance_USD']},{R['Vessel_ID']},$A{i},{h1})"
             f"/SUMIFS({R['Budget_USD']},{R['Vessel_ID']},$A{i},{h1})", PCT, LINK_FONT)
        for col, y in zip("OPQ", [2024, 2025, 2026]):
            _set(ws, f"{col}{i}",
                 f"=SUMIFS({R['Variance_USD']},{R['Vessel_ID']},$A{i},{R['Year']},{y})"
                 f"/SUMIFS({R['Budget_USD']},{R['Vessel_ID']},$A{i},{R['Year']},{y})", PCT, LINK_FONT)
        _set(ws, f"R{i}", int(r.Months_Over_Budget))
        _set(ws, f"S{i}", int(r.Longest_Over_Run))
        _set(ws, f"T{i}", float(r.Urgent_Share), PCT)
        _set(ws, f"U{i}",
             f'=IF(OR(L{i}>0,J{i}>=Assumptions!$B$5),"Poor",'
             f'IF(J{i}>=Assumptions!$B$6,"Watch","Controlled"))', None, LINK_FONT)
        _set(ws, f"V{i}", "Yes" if r.Has_Handover_Record else "No record")
        for col, v, fmt in [("W", r.Open_Issues, "0"), ("X", r.Overdue_Issues, "0"),
                            ("Y", r.Deferred_Exposure_USD, USD)]:
            _set(ws, f"{col}{i}", _value(v), fmt)
        _set(ws, f"Z{i}", _value(r.Handover_Risk))
        _set(ws, f"AA{i}", _value(r.Primary_Owner))
    t = last + 1
    _set(ws, f"B{t}", "Fleet", font=BOLD_FONT)
    for col in "GHILM":
        _set(ws, f"{col}{t}", f"=SUM({col}5:{col}{last})", USD, BOLD_FONT)
    _set(ws, f"J{t}", f"=I{t}/G{t}", PCT, BOLD_FONT)
    _set(ws, f"Y{t}", f"=SUM(Y5:Y{last})", USD, BOLD_FONT)
    for j in range(1, len(headers) + 1):
        ws.cell(row=t, column=j).border = TOTAL_BORDER
    _set(ws, f"A{t + 2}",
         "Months over budget and longest run count vessel-months with total variance above zero "
         "(31 months). Blank handover fields mean no record, not zero.", font=NOTE_FONT)
    widths = {"A": 10, "B": 13, "C": 16, "D": 7, "E": 9, "F": 16, "U": 11, "V": 11, "Z": 10, "AA": 12}
    for j in range(1, len(headers) + 1):
        L = get_column_letter(j)
        ws.column_dimensions[L].width = widths.get(L, 12)
    ws.freeze_panes = "C5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{last}"


def sheet_category(wb, cat: pd.DataFrame):
    ws = wb.create_sheet("Category_Trend")
    _title(ws, "Cost category trend",
           "SUMIFS formulas over Fact_Monthly. Yearly rates are variance / budget for that year; "
           "2026 is seven months.")
    headers = ["Cost_Category", "Budget_USD", "Actual_USD", "Variance_USD", "Variance_Pct",
               "NonBudgeted_Spend_USD", "Budgeted_Gap_USD", "Budget_Share", "Var_Pct_2024",
               "Var_Pct_2025", "Var_Pct_2026", "Change_2024_to_2026_Pct_Points"]
    _header(ws, 4, headers)
    last = 4 + len(cat)
    for i, c in enumerate(cat["Cost_Category"], start=5):
        _set(ws, f"A{i}", c)
        for col, src in zip("BCD", ["Budget_USD", "Actual_USD", "Variance_USD"]):
            _set(ws, f"{col}{i}", f"=SUMIFS({R[src]},{R['Cost_Category']},$A{i})", USD, LINK_FONT)
        _set(ws, f"E{i}", f"=D{i}/B{i}", PCT)
        _set(ws, f"F{i}", f"=SUMIFS({R['NonBudgeted_Spend_USD']},{R['Cost_Category']},$A{i})", USD, LINK_FONT)
        _set(ws, f"G{i}", f"=SUMIFS({R['Budgeted_Gap_USD']},{R['Cost_Category']},$A{i})", USD, LINK_FONT)
        _set(ws, f"H{i}", f"=B{i}/SUM($B$5:$B${last})", PCT)
        for col, y in zip("IJK", [2024, 2025, 2026]):
            _set(ws, f"{col}{i}",
                 f"=SUMIFS({R['Variance_USD']},{R['Cost_Category']},$A{i},{R['Year']},{y})"
                 f"/SUMIFS({R['Budget_USD']},{R['Cost_Category']},$A{i},{R['Year']},{y})", PCT, LINK_FONT)
        _set(ws, f"L{i}", f"=K{i}-I{i}", PCT)
    t = last + 1
    _set(ws, f"A{t}", "Fleet", font=BOLD_FONT)
    for col in "BCDFG":
        _set(ws, f"{col}{t}", f"=SUM({col}5:{col}{last})", USD, BOLD_FONT)
    _set(ws, f"E{t}", f"=D{t}/B{t}", PCT, BOLD_FONT)
    for j in range(1, len(headers) + 1):
        ws.cell(row=t, column=j).border = TOTAL_BORDER
    ws.column_dimensions["A"].width = 24
    for j in range(2, len(headers) + 1):
        ws.column_dimensions[get_column_letter(j)].width = 14
    ws.freeze_panes = "B5"


# ---------------------------------------------------------------- value sheets


def sheet_readme(wb, snapshot: dict):
    ws = wb.active
    ws.title = "Read_Me"
    _title(ws, "GNMTC vessel cost control: analysis workbook",
           f"Built {datetime.now():%Y-%m-%d %H:%M} from {snapshot['file']} "
           f"(modified {snapshot['modified']}, {snapshot['bytes']:,} bytes). Synthetic data only.")
    rows = [
        ("Purpose", "Working analysis file for the vessel cost control assessment: how the source "
                    "data was used, what it shows, and the controls that follow."),
        ("Rebuild", "From the Assignment2 folder run:  py -3 -m analysis.run_all"),
        ("Source rows", f"{snapshot['rows_vessels']} vessels; {snapshot['rows_monthly']:,} monthly "
                        f"rows; {snapshot['rows_transactions']:,} transactions; "
                        f"{snapshot['rows_handover']} handover rows."),
        ("Validation", "Reconciliation sheet. Column-level profiling is in "
                       "GNMTC_Data_Quality_Assessment.xlsx."),
        ("Colour key", "Black = values or same-sheet formulas. Green = formulas that read another "
                       "sheet. Blue on yellow = threshold inputs you can change (Assumptions). "
                       "Blue = hard-coded Python check values."),
        ("Key identity", "Variance = non-budgeted spend + (budgeted lines vs budget), on every row."),
        ("Unbudgeted spend", "Taken from Budget_Status on transactions. Off_Budget_USD is kept as a "
                             "source column only; it does not reconcile (Reconciliation, E10)."),
    ]
    for i, (k, v) in enumerate(rows, start=4):
        _set(ws, f"A{i}", k, font=BOLD_FONT)
        _set(ws, f"B{i}", v)
        ws[f"B{i}"].alignment = Alignment(wrap_text=True, vertical="top")
    start = 4 + len(rows) + 2
    _set(ws, f"A{start}", "Sheet guide", font=BOLD_FONT)
    guide = [
        ("Reconciliation", "D1", "Source checks with expected and actual results"),
        ("Fact_Monthly", "D1", "Analytical dataset: vessel x month x category, 3,472 rows"),
        ("Fleet_Bridge", "D1, D2", "Budget to actual by year, with Python cross-checks"),
        ("Vessel_Scorecard", "D1, D2", "One row per vessel: cost, persistence, handover fields"),
        ("Category_Trend", "D1, D2", "Category totals and yearly rates"),
        ("Hotspots", "D2, D3", "Largest vessel-category overruns and savings"),
        ("Hotspot_Themes", "D3", "What was bought in each overrun hotspot"),
        ("Urgency", "D3", "Urgent spend by category"),
        ("Handover_Matrix", "D2, D4", "Cost band against deferred exposure, with decision"),
        ("Fleet_Alerts", "D5", "Quarterly repairs and safety rates against 2024"),
        ("EW_Latest", "D5", "Early-warning levels for the latest month (July 2026)"),
        ("EW_Scores", "D5", "Early-warning features and level for every vessel-month"),
        ("EW_Backtest", "D5", "Precision, recall and false alarms by method and period"),
        ("EW_Rule_Selection", "D5", "Candidate rules; choice made on the tuning period"),
        ("EW_First_Flags", "D5", "First Watch and Escalate month per vessel"),
        ("Evidence_Register", "D3", "Each major claim with figure, source and fact/interpretation"),
        ("Control_Register", "D4", "Recommended controls: continue, change, monitor, new"),
        ("Assumptions", "All", "Thresholds and treatment decisions"),
    ]
    _header(ws, start + 1, ["Sheet", "Deliverable", "Contents"])
    for i, (s, d, c) in enumerate(guide, start=start + 2):
        _set(ws, f"A{i}", s)
        ws[f"A{i}"].hyperlink = f"#'{s}'!A1"
        ws[f"A{i}"].font = Font(name=FONT, size=10, color="0563C1", underline="single")
        _set(ws, f"B{i}", d)
        _set(ws, f"C{i}", c)
    _set(ws, f"A{start + 3 + len(guide)}",
         "D1 analysis file, D2 management summary, D3 evidence and limitations, "
         "D4 recommendations, D5 early-warning prototype (brief section 7).", font=NOTE_FONT)
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 95
    ws.column_dimensions["C"].width = 60


def sheet_assumptions(wb, assumptions: pd.DataFrame):
    ws = wb.create_sheet("Assumptions")
    _title(ws, "Assumptions and thresholds",
           "Blue-on-yellow cells are inputs. Changing B5 or B6 re-bands the Vessel_Scorecard; "
           "other thresholds are applied in the Python build (analysis/config.py).")
    _header(ws, 4, ["Input", "Value", "Used by"])
    inputs = [
        ("Cost band Poor: variance at or above", config.COST_BAND_POOR_PCT, PCT, "Vessel_Scorecard"),
        ("Cost band Watch: variance at or above", config.COST_BAND_WATCH_PCT, PCT, "Vessel_Scorecard"),
        ("Deferred exposure material at or above", config.DEFERRED_MATERIAL_USD, USD, "Handover_Matrix (Python)"),
    ]
    for i, (k, v, fmt, use) in enumerate(inputs, start=5):
        _set(ws, f"A{i}", k)
        _set(ws, f"B{i}", v, fmt, INPUT_FONT)
        ws[f"B{i}"].fill = INPUT_FILL
        _set(ws, f"C{i}", use)
    write_frame(ws, assumptions, start_row=10, widths={"Item": 32, "Treatment": 60, "Reason": 70},
                wrap=("Treatment", "Reason"), freeze=False, autofilter=False)
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 60
    ws.column_dimensions["C"].width = 70


def build_workbook(path, snapshot, checks: pd.DataFrame, fact: pd.DataFrame, tables: dict,
                   bt: dict, evidence: pd.DataFrame, controls: pd.DataFrame,
                   assumptions: pd.DataFrame, latest: pd.DataFrame) -> None:
    wb = Workbook()
    sheet_readme(wb, snapshot)

    ws = wb.create_sheet("Reconciliation")
    _title(ws, "Source reconciliation",
           "Fail stops the build. Known issue = documented discrepancy that the analysis works around.")
    write_frame(ws, checks, widths={"Check": 46, "Expected": 34, "Actual": 52, "Status": 12,
                                    "Note": 80}, wrap=("Actual", "Note"))

    ws = wb.create_sheet(FACT)
    fact_out = fact.copy()
    fact_out["Is_Partial_Year"] = fact_out["Is_Partial_Year"].map({True: "Yes", False: "No"})
    fact_out["Has_Handover_Record"] = fact_out["Has_Handover_Record"].map({True: "Yes", False: "No"})
    fact_out["Overdue_Exceeds_Open"] = fact_out["Overdue_Exceeds_Open"].map({True: "Yes", False: "No"})
    _header(ws, 1, list(fact_out.columns))
    fmts = {j: _fmt_for(c) for j, c in enumerate(fact_out.columns, start=1)}
    for i, row in enumerate(fact_out.itertuples(index=False), start=2):
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=i, column=j, value=_value(v))
            if fact_out.columns[j - 1] == "Period":
                c.number_format = DATE
            elif fmts[j]:
                c.number_format = USD_CENTS if fmts[j] == USD else fmts[j]
    for j, col in enumerate(fact_out.columns, start=1):
        ws.column_dimensions[get_column_letter(j)].width = min(max(len(col) * 0.9 + 2, 9), 22)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(fact_out.columns))}{len(fact_out) + 1}"

    sheet_bridge(wb, tables["bridge"])
    sheet_scorecard(wb, tables["scorecard"])
    sheet_category(wb, tables["category"])

    ws = wb.create_sheet("Hotspots")
    _title(ws, "Vessel x category hotspots",
           "Fifteen largest overruns and ten largest savings over 31 months. Repeated = over budget "
           "in at least 65% of months.")
    hot = tables["hotspots"][["Type", "Vessel_ID", "Vessel_Name", "Cost_Category", "Budget_USD",
                              "Actual_USD", "Variance_USD", "Variance_Pct", "NonBudgeted_Spend_USD",
                              "Budgeted_Gap_USD", "Months_Over_Budget", "Months_Over_10pct",
                              "Pattern"]]
    write_frame(ws, hot, widths={"Cost_Category": 22})

    ws = wb.create_sheet("Hotspot_Themes")
    _title(ws, "What was bought in each overrun hotspot",
           "Description themes are invoice labels. They describe the spend, not why it was needed.")
    write_frame(ws, tables["hotspot_themes"], widths={"Cost_Category": 22, "Description_Theme": 24})

    ws = wb.create_sheet("Urgency")
    _title(ws, "Urgent spend by category", "Urgency criteria are not defined in the source.")
    write_frame(ws, tables["urgency"], widths={"Cost_Category": 22})

    ws = wb.create_sheet("Handover_Matrix")
    _title(ws, "Handover decision matrix",
           "Two separate questions: cost control (Cost_Band) and recorded deferred exposure "
           "(Handover_Axis). Handover_Risk is the unvalidated source label.")
    write_frame(ws, tables["handover"], widths={"Decision": 55, "Data_Caveat": 48},
                wrap=("Decision", "Data_Caveat"))

    ws = wb.create_sheet("Fleet_Alerts")
    _title(ws, "Fleet alert: repairs and safety against the 2024 rate",
           "2024 quarters form the baseline and are not alerted. 2026Q3 is July only.")
    write_frame(ws, bt["fleet_alerts"], widths={"Cost_Category": 22})

    ws = wb.create_sheet("EW_Latest")
    _title(ws, "Early warning: latest month",
           "Level for each vessel on the most recent closed month. Escalate needs a written "
           "explanation; two consecutive Escalates go to management review.")
    write_frame(ws, latest, widths={"Reasons": 70, "Hot_Category": 22}, wrap=("Reasons",))

    ws = wb.create_sheet("EW_Scores")
    _title(ws, "Early warning: every vessel-month",
           "Features use months up to and including Period. Next_* columns are the outcome "
           "window (following three months) and are blank where it is incomplete.")
    cols = ["Vessel_ID", "Vessel_Name", "Period", "History_Months", "Level", "Reasons",
            "Var_Pct_3m", "Var_Pct_6m", "Months_Over_6m", "NonBudgeted_3m_USD",
            "Hot_Category_Months_6m", "Hot_Category", "Technical_Var_Pct_3m", "Urgent_Share_3m",
            "Baseline_Flag", "Planned_Escalate", "Logistic_Prob", "Next_Var_Pct",
            "Next_NonBudgeted_USD", "Outcome_Bad"]
    sc = bt["scored"][cols].copy()
    sc["Outcome_Bad"] = sc["Outcome_Bad"].map({1.0: "Bad", 0.0: "OK"})
    for c in ("Baseline_Flag", "Planned_Escalate"):
        sc[c] = sc[c].map({True: "Yes", False: "No"})
    write_frame(ws, sc, widths={"Reasons": 60, "Hot_Category": 22})

    ws = wb.create_sheet("EW_Backtest")
    _title(ws, "Early warning: backtest results",
           "A flag is a prediction that the next three months will be bad. Precision = share of "
           "flags that were right; recall = share of bad outcomes flagged; false alarm rate = "
           "share of good vessel-months flagged.")
    end = write_frame(ws, bt["metrics"], widths={"Method": 46, "Period": 20})
    lr = bt["logistic"]
    note = (f"Logistic regression: trained on {lr['train_period']} ({lr['train_rows']} rows), "
            f"threshold {lr['threshold']} chosen on {lr['tune_period']}, tested on "
            f"{lr['test_period']}. Coefficients (standardised): "
            + ", ".join(f"{k} {v:+.2f}" for k, v in lr["coefficients"].items()) + ".")
    _set(ws, f"A{end + 2}", note, font=NOTE_FONT)

    ws = wb.create_sheet("EW_Rule_Selection")
    sel = bt["selection"]
    _title(ws, "Early warning: rule selection",
           f"The rule was chosen on the tuning period ({sel.attrs['tune_period']}) only. "
           f"Test columns ({sel.attrs['test_period']}) are shown for transparency.")
    write_frame(ws, sel, widths={"Candidate": 56})

    ws = wb.create_sheet("EW_First_Flags")
    _title(ws, "Early warning: first flag by vessel",
           "Focus = vessels with non-budgeted spend. Controlled = vessels under or near budget.")
    write_frame(ws, bt["first_flags"])

    ws = wb.create_sheet("Evidence_Register")
    _title(ws, "Evidence register (D3)",
           "Fact = computed from the source. Interpretation = a reasonable reading that needs more "
           "evidence. Open = the data cannot answer it.")
    write_frame(ws, evidence, widths={"ID": 6, "Area": 14, "Claim": 52, "Figure": 62,
                                      "Workbook_Source": 26, "Type": 14, "Confidence": 11,
                                      "Caveat": 50}, wrap=("Claim", "Figure", "Caveat"))

    ws = wb.create_sheet("Control_Register")
    _title(ws, "Control register (D4)",
           "Decision types follow brief section 9: continue, change, monitor, and controls to have "
           "in place before taking on another vessel.")
    write_frame(ws, controls, widths={"ID": 6, "Decision_Type": 16, "Control": 60, "Trigger": 40,
                                      "Frequency": 14, "Owner_Function": 15, "Evidence": 14,
                                      "Data_Needed": 36}, wrap=("Control", "Trigger", "Data_Needed"))

    sheet_assumptions(wb, assumptions)

    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False if ws.title in ("Read_Me",) else True
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
