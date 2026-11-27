from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from . import config


@dataclass
class Source:
    vessels: pd.DataFrame
    monthly: pd.DataFrame
    transactions: pd.DataFrame
    handover: pd.DataFrame
    snapshot: dict


def _strip_text(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
    return df


def load_source(path=config.SOURCE_XLSX) -> Source:
    sheets = pd.read_excel(path, sheet_name=list(config.SHEETS.values()))
    vessels = _strip_text(sheets[config.SHEETS["vessels"]].copy())
    monthly = _strip_text(sheets[config.SHEETS["monthly"]].copy())
    transactions = _strip_text(sheets[config.SHEETS["transactions"]].copy())
    handover = _strip_text(sheets[config.SHEETS["handover"]].copy())

    monthly["Period"] = pd.to_datetime(monthly["Period"]).dt.to_period("M").dt.to_timestamp()
    transactions["Transaction_Date"] = pd.to_datetime(transactions["Transaction_Date"])
    transactions["Period"] = transactions["Transaction_Date"].dt.to_period("M").dt.to_timestamp()

    stat = path.stat()
    snapshot = {
        "file": path.name,
        "bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "rows_vessels": len(vessels),
        "rows_monthly": len(monthly),
        "rows_transactions": len(transactions),
        "rows_handover": len(handover),
    }
    return Source(vessels, monthly, transactions, handover, snapshot)
