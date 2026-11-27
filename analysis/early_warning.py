"""Monthly early-warning rule for vessel cost control, with a walk-forward backtest.

Features for month t use months up to and including t. The outcome uses months t+1 to
t+H only. Months without a complete outcome window are scored but not evaluated.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from . import config

FEATURES = [
    "Var_Pct_3m", "Var_Pct_6m", "Months_Over_6m", "NonBudgeted_3m_USD",
    "Hot_Category_Months_6m", "Technical_Var_Pct_3m", "Urgent_Share_3m",
]


def _panel(fact: pd.DataFrame) -> pd.DataFrame:
    """One row per vessel-month with the inputs the features need."""
    vm = fact.groupby(["Vessel_ID", "Vessel_Name", "Period"], as_index=False).agg(
        Budget_USD=("Budget_USD", "sum"),
        Actual_USD=("Actual_USD", "sum"),
        Variance_USD=("Variance_USD", "sum"),
        NonBudgeted_USD=("NonBudgeted_Spend_USD", "sum"),
        Urgent_USD=("Urgent_Spend_USD", "sum"),
    )
    tech = fact[fact["Cost_Category"].isin(config.TECHNICAL_CATEGORIES)].groupby(
        ["Vessel_ID", "Period"])[["Budget_USD", "Variance_USD"]].sum().rename(
        columns={"Budget_USD": "Tech_Budget_USD", "Variance_USD": "Tech_Variance_USD"})
    hot = (fact.assign(Hot=fact["Variance_Pct"] > config.EW_CATEGORY_HOT_PCT)
           .pivot_table(index=["Vessel_ID", "Period"], columns="Cost_Category",
                        values="Hot", aggfunc="max", fill_value=False))
    hot.columns = [f"Hot::{c}" for c in hot.columns]
    vm = vm.merge(tech.reset_index(), on=["Vessel_ID", "Period"]).merge(
        hot.reset_index(), on=["Vessel_ID", "Period"])
    return vm.sort_values(["Vessel_ID", "Period"]).reset_index(drop=True)


def _features_for_vessel(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("Period").copy()
    roll = lambda s, n: s.rolling(n, min_periods=n).sum()
    g["History_Months"] = np.arange(1, len(g) + 1)
    g["Var_Pct_3m"] = roll(g["Variance_USD"], 3) / roll(g["Budget_USD"], 3)
    g["Var_Pct_6m"] = roll(g["Variance_USD"], 6) / roll(g["Budget_USD"], 6)
    g["Months_Over_6m"] = roll((g["Variance_USD"] > 0).astype(int), 6)
    g["NonBudgeted_3m_USD"] = roll(g["NonBudgeted_USD"], 3)
    g["Technical_Var_Pct_3m"] = roll(g["Tech_Variance_USD"], 3) / roll(g["Tech_Budget_USD"], 3)
    g["Urgent_Share_3m"] = roll(g["Urgent_USD"], 3) / roll(g["Actual_USD"], 3)
    hot_cols = [c for c in g.columns if c.startswith("Hot::")]
    hot_counts = pd.concat(
        [g[c].astype(int).rolling(config.EW_CATEGORY_HOT_WINDOW,
                                  min_periods=config.EW_CATEGORY_HOT_WINDOW).sum().rename(c)
         for c in hot_cols], axis=1)
    g["Hot_Category_Months_6m"] = hot_counts.max(axis=1)
    g["Hot_Category"] = hot_counts.fillna(-1).idxmax(axis=1).str.replace("Hot::", "", regex=False)
    g.loc[g["Hot_Category_Months_6m"].isna(), "Hot_Category"] = None

    h = config.EW_HORIZON_MONTHS
    fwd = lambda s: s[::-1].rolling(h, min_periods=h).sum()[::-1].shift(-1)
    g["Next_Var_USD"] = fwd(g["Variance_USD"])
    g["Next_Budget_USD"] = fwd(g["Budget_USD"])
    g["Next_NonBudgeted_USD"] = fwd(g["NonBudgeted_USD"])
    g["Next_Var_Pct"] = g["Next_Var_USD"] / g["Next_Budget_USD"]
    return g.drop(columns=hot_cols)


def build_features(fact: pd.DataFrame) -> pd.DataFrame:
    panel = _panel(fact)
    out = pd.concat([_features_for_vessel(g) for _, g in panel.groupby("Vessel_ID")],
                    ignore_index=True)
    out["Has_Outcome"] = out["Next_Budget_USD"].notna()
    out["Outcome_Bad"] = np.where(
        out["Has_Outcome"],
        (out["Next_Var_Pct"] > config.EW_OUTCOME_VAR_PCT)
        | (out["Next_NonBudgeted_USD"] > config.EW_OUTCOME_NONBUDGET_USD),
        np.nan)
    return out


def apply_rule(feat: pd.DataFrame, variant: str = "selected") -> pd.DataFrame:
    """Assign Watch / Escalate levels.

    "planned" escalates on a hot category as well; "selected" moves that trigger to Watch,
    because it fired on well-controlled vessels in the June 2024 to September 2025 tuning period.
    """
    f = feat.copy()
    eligible = f["History_Months"] >= config.EW_MIN_HISTORY_MONTHS
    hot = (f["Hot_Category_Months_6m"] >= config.EW_CATEGORY_HOT_MONTHS,
           "category over 10% in 4 of last 6 months")
    escalate_reasons = [
        (f["Var_Pct_3m"] > config.EW_ESCALATE_VAR3_PCT, "3-month variance above 5%"),
        (f["NonBudgeted_3m_USD"] > config.EW_NONBUDGET_ESCALATE_USD,
         "non-budgeted spend above $10,000 in 3 months"),
    ]
    watch_reasons = [
        (f["Var_Pct_3m"] > config.EW_WATCH_VAR3_PCT, "3-month variance above 3%"),
        (f["NonBudgeted_3m_USD"] > 0, "non-budgeted spend in last 3 months"),
    ]
    if variant == "planned":
        escalate_reasons.insert(1, hot)
    elif variant == "selected":
        watch_reasons.append(hot)
    else:
        raise ValueError(f"Unknown rule variant: {variant}")
    esc = np.zeros(len(f), dtype=bool)
    wat = np.zeros(len(f), dtype=bool)
    reasons = [[] for _ in range(len(f))]
    for mask, text in escalate_reasons:
        mask = (mask & eligible).to_numpy()
        esc |= mask
        for i in np.flatnonzero(mask):
            reasons[i].append(text)
    for mask, text in watch_reasons:
        mask = (mask & eligible).to_numpy()
        wat |= mask
        for i in np.flatnonzero(mask & ~esc):
            reasons[i].append(text)
    f["Level"] = np.select([~eligible.to_numpy(), esc, wat],
                           ["Insufficient history", "Escalate", "Watch"], default="None")
    f["Reasons"] = [
        "; ".join(r) + (f" ({c})" if any("category" in x for x in r) and c else "")
        for r, c in zip(reasons, f["Hot_Category"])]
    f["Escalate"] = f["Level"] == "Escalate"
    f["Watch_Or_Escalate"] = f["Level"].isin(["Escalate", "Watch"])
    return f


def naive_baseline(feat: pd.DataFrame) -> pd.Series:
    """Flag when the single latest month is more than 5% over budget."""
    last = feat["Variance_USD"] / feat["Budget_USD"]
    eligible = feat["History_Months"] >= config.EW_MIN_HISTORY_MONTHS
    return (last > config.EW_ESCALATE_VAR3_PCT) & eligible


def _split(period: pd.Series) -> pd.Series:
    return np.select(
        [period <= pd.Timestamp(config.EW_TRAIN_END), period <= pd.Timestamp(config.EW_TUNE_END)],
        ["2024 (Jun-Dec)", "2025"], default="2026 (Jan-Apr)")


def _metrics(pred: pd.Series, actual: pd.Series) -> dict:
    pred = pred.astype(bool)
    actual = actual.astype(bool)
    tp = int((pred & actual).sum())
    fp = int((pred & ~actual).sum())
    fn = int((~pred & actual).sum())
    tn = int((~pred & ~actual).sum())
    return {
        "Vessel_Months": len(pred), "Bad_Outcomes": int(actual.sum()), "Flags": int(pred.sum()),
        "True_Positive": tp, "False_Positive": fp, "Missed": fn, "True_Negative": tn,
        "Precision": tp / (tp + fp) if tp + fp else np.nan,
        "Recall": tp / (tp + fn) if tp + fn else np.nan,
        "False_Alarm_Rate": fp / (fp + tn) if fp + tn else np.nan,
    }


def logistic_comparison(scored: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Train on outcomes fully inside 2024, choose the threshold on 2025, report on 2026."""
    ev = scored[scored["Has_Outcome"] & (scored["History_Months"] >= config.EW_MIN_HISTORY_MONTHS)]
    ev = ev.dropna(subset=FEATURES)
    last_train_t = pd.Timestamp(config.EW_TRAIN_END) - pd.DateOffset(months=config.EW_HORIZON_MONTHS)
    last_tune_t = pd.Timestamp(config.EW_TUNE_END) - pd.DateOffset(months=config.EW_HORIZON_MONTHS)
    train = ev[ev["Period"] <= last_train_t]
    tune = ev[(ev["Period"] > pd.Timestamp(config.EW_TRAIN_END)) & (ev["Period"] <= last_tune_t)]
    test = ev[ev["Period"] > pd.Timestamp(config.EW_TUNE_END)]

    scaler = StandardScaler().fit(train[FEATURES])
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(scaler.transform(train[FEATURES]), train["Outcome_Bad"].astype(int))

    p_tune = model.predict_proba(scaler.transform(tune[FEATURES]))[:, 1]
    best_t, best_f1 = 0.5, -1.0
    for t in np.arange(0.2, 0.81, 0.05):
        m = _metrics(pd.Series(p_tune >= t), tune["Outcome_Bad"].reset_index(drop=True))
        p, r = m["Precision"], m["Recall"]
        f1 = 2 * p * r / (p + r) if p and r and not np.isnan(p) and not np.isnan(r) else 0
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1

    prob = pd.Series(np.nan, index=scored.index)
    ok = scored[FEATURES].notna().all(axis=1) & (scored["History_Months"] >= config.EW_MIN_HISTORY_MONTHS)
    prob[ok] = model.predict_proba(scaler.transform(scored.loc[ok, FEATURES]))[:, 1]
    info = {
        "train_rows": len(train), "tune_rows": len(tune), "test_rows": len(test),
        "train_period": f"{train['Period'].min():%b %Y} to {train['Period'].max():%b %Y}",
        "tune_period": f"{tune['Period'].min():%b %Y} to {tune['Period'].max():%b %Y}",
        "test_period": f"{test['Period'].min():%b %Y} to {test['Period'].max():%b %Y}",
        "threshold": round(best_t, 2),
        "coefficients": dict(zip(FEATURES, np.round(model.coef_[0], 3))),
    }
    return prob, info


RULE_CANDIDATES = {
    "Planned: 3m var > 5%, hot category, or non-budgeted > $10k":
        lambda d: (d["Var_Pct_3m"] > 0.05) | (d["Hot_Category_Months_6m"] >= 4)
                  | (d["NonBudgeted_3m_USD"] > 10_000),
    "Selected: 3m var > 5% or non-budgeted > $10k":
        lambda d: (d["Var_Pct_3m"] > 0.05) | (d["NonBudgeted_3m_USD"] > 10_000),
    "Hot category needs 5 of 6 months":
        lambda d: (d["Var_Pct_3m"] > 0.05) | (d["Hot_Category_Months_6m"] >= 5)
                  | (d["NonBudgeted_3m_USD"] > 10_000),
    "3m var > 5% and 6m var > 3%, or non-budgeted > $10k":
        lambda d: ((d["Var_Pct_3m"] > 0.05) & (d["Var_Pct_6m"] > 0.03))
                  | (d["NonBudgeted_3m_USD"] > 10_000),
    "3m var > 5% or any non-budgeted":
        lambda d: (d["Var_Pct_3m"] > 0.05) | (d["NonBudgeted_3m_USD"] > 0),
    "Baseline: last month > 5%":
        lambda d: (d["Variance_USD"] / d["Budget_USD"]) > 0.05,
}


def rule_selection(feat: pd.DataFrame) -> pd.DataFrame:
    """Candidate escalation rules. The choice is made on the tuning columns only."""
    ev = feat[feat["Has_Outcome"] & (feat["History_Months"] >= config.EW_MIN_HISTORY_MONTHS)]
    last_tune_t = pd.Timestamp(config.EW_TUNE_END) - pd.DateOffset(months=config.EW_HORIZON_MONTHS)
    tune = ev[ev["Period"] <= last_tune_t]
    test = ev[ev["Period"] > pd.Timestamp(config.EW_TUNE_END)]
    rows = []
    for name, fn in RULE_CANDIDATES.items():
        mt, ms = _metrics(fn(tune), tune["Outcome_Bad"]), _metrics(fn(test), test["Outcome_Bad"])
        rows.append({"Candidate": name,
                     "Tune_Flags": mt["Flags"], "Tune_Precision": mt["Precision"],
                     "Tune_Recall": mt["Recall"], "Tune_False_Alarm_Rate": mt["False_Alarm_Rate"],
                     "Test_Flags": ms["Flags"], "Test_Precision": ms["Precision"],
                     "Test_Recall": ms["Recall"], "Test_False_Alarm_Rate": ms["False_Alarm_Rate"],
                     "Chosen": name.startswith("Selected")})
    out = pd.DataFrame(rows)
    out.attrs["tune_period"] = f"{tune['Period'].min():%b %Y} to {tune['Period'].max():%b %Y}"
    out.attrs["test_period"] = f"{test['Period'].min():%b %Y} to {test['Period'].max():%b %Y}"
    return out


def backtest(fact: pd.DataFrame) -> dict:
    feat = build_features(fact)
    scored = apply_rule(feat, "selected")
    planned = apply_rule(feat, "planned")
    scored["Planned_Escalate"] = planned["Escalate"]
    scored["Baseline_Flag"] = naive_baseline(scored)
    prob, lr_info = logistic_comparison(scored)
    scored["Logistic_Prob"] = prob
    scored["Logistic_Flag"] = prob >= lr_info["threshold"]

    ev = scored[scored["Has_Outcome"] & (scored["History_Months"] >= config.EW_MIN_HISTORY_MONTHS)].copy()
    ev["Split"] = _split(ev["Period"])
    ev["Outcome_Variance_Only"] = (ev["Next_Var_Pct"] > config.EW_OUTCOME_VAR_PCT).astype(float)

    rows = []
    methods = {
        "Selected rule: Escalate": "Escalate",
        "Selected rule: Watch or Escalate": "Watch_Or_Escalate",
        "Planned rule: Escalate": "Planned_Escalate",
        "Baseline: last month > 5%": "Baseline_Flag",
        "Logistic regression": "Logistic_Flag",
    }
    for outcome, label_suffix in [("Outcome_Bad", ""),
                                  ("Outcome_Variance_Only", " [variance-only outcome]")]:
        for label, col in methods.items():
            if outcome != "Outcome_Bad" and col not in ("Escalate", "Baseline_Flag"):
                continue
            for split, part in [("All evaluated months", ev)] + list(ev.groupby("Split")):
                if col == "Logistic_Flag" and split in ("All evaluated months", "2024 (Jun-Dec)"):
                    continue
                rows.append({"Method": label + label_suffix, "Period": split,
                             **_metrics(part[col], part[outcome])})
    metrics = pd.DataFrame(rows)

    first = []
    names = scored.drop_duplicates("Vessel_ID").set_index("Vessel_ID")["Vessel_Name"]
    for vid in names.index:
        g = scored[scored["Vessel_ID"] == vid]
        esc = g[g["Level"] == "Escalate"]
        watch = g[g["Level"].isin(["Watch", "Escalate"])]
        evg = ev[ev["Vessel_ID"] == vid]
        first.append({
            "Vessel_ID": vid, "Vessel_Name": names[vid],
            "Group": "Focus" if vid in config.FOCUS_VESSELS
                     else "Controlled" if vid in config.CONTROLLED_VESSELS else "Other",
            "First_Watch": watch["Period"].min(),
            "First_Escalate": esc["Period"].min(),
            "Escalate_Months": len(esc),
            "Watch_Months": int((g["Level"] == "Watch").sum()),
            "Scored_Months": int((g["History_Months"] >= config.EW_MIN_HISTORY_MONTHS).sum()),
            "Bad_Outcome_Months": int(evg["Outcome_Bad"].sum()),
            "Evaluated_Months": len(evg),
            "First_Bad_Outcome": evg.loc[evg["Outcome_Bad"] == 1, "Period"].min(),
        })
    first = pd.DataFrame(first).sort_values(["Group", "Vessel_Name"]).reset_index(drop=True)

    workload = scored[scored["History_Months"] >= config.EW_MIN_HISTORY_MONTHS].groupby("Period").agg(
        Escalate=("Escalate", "sum"), Watch=("Level", lambda s: int((s == "Watch").sum()))
    ).reset_index()

    return {"scored": scored, "metrics": metrics, "first_flags": first,
            "workload": workload, "logistic": lr_info, "fleet_alerts": fleet_alerts(fact),
            "selection": rule_selection(feat)}


def fleet_alerts(fact: pd.DataFrame) -> pd.DataFrame:
    """Quarterly fleet rate for repairs and safety against the baseline-year rate."""
    base = fact[fact["Year"] == config.BASELINE_YEAR].groupby("Cost_Category")[
        ["Variance_USD", "Budget_USD"]].sum()
    base_rate = base["Variance_USD"] / base["Budget_USD"]
    q = fact[fact["Cost_Category"].isin(config.TECHNICAL_CATEGORIES)].groupby(
        ["Quarter", "Cost_Category"]).agg(Variance_USD=("Variance_USD", "sum"),
                                          Budget_USD=("Budget_USD", "sum"),
                                          Months=("Period", "nunique")).reset_index()
    q["Variance_Pct"] = q["Variance_USD"] / q["Budget_USD"]
    q["Baseline_Pct"] = q["Cost_Category"].map(base_rate)
    in_baseline = q["Quarter"].str.startswith(str(config.BASELINE_YEAR))
    q["Fleet_Alert"] = np.where(in_baseline, "Baseline year",
                                np.where(q["Variance_Pct"] > q["Baseline_Pct"] + config.EW_FLEET_ALERT_MARGIN,
                                         "Alert", "OK"))
    return q


def score_latest(fact: pd.DataFrame) -> pd.DataFrame:
    """Rank vessels on the most recent closed month."""
    scored = apply_rule(build_features(fact))
    latest = scored[scored["Period"] == scored["Period"].max()]
    order = {"Escalate": 0, "Watch": 1, "None": 2, "Insufficient history": 3}
    return (latest.assign(_o=latest["Level"].map(order))
            .sort_values(["_o", "Var_Pct_3m"], ascending=[True, False])
            [["Vessel_ID", "Vessel_Name", "Period", "Level", "Reasons", "Var_Pct_3m",
              "Var_Pct_6m", "NonBudgeted_3m_USD", "Hot_Category_Months_6m", "Hot_Category"]]
            .reset_index(drop=True))
