from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_XLSX = ROOT / "Synthetic_GNMTC_Vessel_Cost_Risk_Data (2).xlsx"
DQ_XLSX = ROOT / "GNMTC_Data_Quality_Assessment.xlsx"
OUTPUT_DIR = ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"

SHEETS = {
    "vessels": "Vessel_Master",
    "monthly": "Monthly_Budget_Actual",
    "transactions": "Cost_Transactions",
    "handover": "Handover_Deferred_Risk",
}

CATEGORIES = [
    "Crew Wages",
    "Repairs & Maintenance",
    "Spares",
    "Stores",
    "Crew Travel",
    "Logistics & Freight",
    "Safety & Compliance",
    "Other Operating Cost",
]
TECHNICAL_CATEGORIES = ["Repairs & Maintenance", "Safety & Compliance"]

FIRST_PERIOD = "2024-01-01"
LAST_PERIOD = "2026-07-01"
PARTIAL_YEAR = 2026
BASELINE_YEAR = 2024

TXN_ROLLUP_TOLERANCE_USD = 0.02
VARIANCE_TOLERANCE_USD = 0.01

# Vessel-level cost bands used by findings and the handover matrix.
COST_BAND_POOR_PCT = 0.04
COST_BAND_WATCH_PCT = 0.02
DEFERRED_MATERIAL_USD = 120_000

# Early-warning rule.
EW_MIN_HISTORY_MONTHS = 6
EW_WATCH_VAR3_PCT = 0.03
EW_ESCALATE_VAR3_PCT = 0.05
EW_CATEGORY_HOT_PCT = 0.10
EW_CATEGORY_HOT_MONTHS = 4
EW_CATEGORY_HOT_WINDOW = 6
EW_NONBUDGET_ESCALATE_USD = 10_000
# Fleet alert fires only when a quarter's rate exceeds its 2024 rate by this margin
# (without it, a 2024 safety rate of +0.1% makes any positive quarter an alert).
EW_FLEET_ALERT_MARGIN = 0.02

# Outcome the rule is evaluated against: the next three months.
EW_HORIZON_MONTHS = 3
EW_OUTCOME_VAR_PCT = 0.05
EW_OUTCOME_NONBUDGET_USD = 10_000

EW_TRAIN_END = "2024-12-01"
EW_TUNE_END = "2025-12-01"

FOCUS_VESSELS = ["V1008", "V1005", "V1002", "V1011", "V1013"]
CONTROLLED_VESSELS = ["V1001", "V1006", "V1007", "V1010"]
