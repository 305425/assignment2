import pandas as pd
import pytest

from analysis import config
from analysis import early_warning as ew

FEATURE_COLS = ew.FEATURES + ["History_Months", "Hot_Category"]


@pytest.fixture(scope="module")
def features(fact):
    return ew.build_features(fact)


@pytest.mark.parametrize("cutoff", ["2024-09-01", "2025-06-01", "2026-03-01"])
def test_features_do_not_use_later_months(fact, features, cutoff):
    cut = pd.Timestamp(cutoff)
    truncated = ew.build_features(fact[fact["Period"] <= cut])
    full = features[features["Period"] <= cut].set_index(["Vessel_ID", "Period"])[FEATURE_COLS]
    part = truncated.set_index(["Vessel_ID", "Period"])[FEATURE_COLS]
    pd.testing.assert_frame_equal(full.sort_index(), part.sort_index(), check_dtype=False)


def test_rule_levels_do_not_use_later_months(fact, features):
    cut = pd.Timestamp("2025-06-01")
    full = ew.apply_rule(features)
    part = ew.apply_rule(ew.build_features(fact[fact["Period"] <= cut]))
    a = full[full["Period"] <= cut].set_index(["Vessel_ID", "Period"])["Level"].sort_index()
    b = part.set_index(["Vessel_ID", "Period"])["Level"].sort_index()
    pd.testing.assert_series_equal(a, b)


def test_outcome_window_is_strictly_after_t(features):
    g = features[features["Vessel_ID"] == "V1008"].sort_values("Period").reset_index(drop=True)
    i = 10
    expected = g.loc[i + 1:i + config.EW_HORIZON_MONTHS, "Variance_USD"].sum()
    assert g.loc[i, "Next_Var_USD"] == pytest.approx(expected)


def test_last_months_have_no_outcome(features):
    last = features["Period"].max()
    tail = features[features["Period"] > last - pd.DateOffset(months=config.EW_HORIZON_MONTHS)]
    assert not tail["Has_Outcome"].any()


def test_first_months_are_not_scored(features):
    levels = ew.apply_rule(features)
    early = levels[levels["History_Months"] < config.EW_MIN_HISTORY_MONTHS]
    assert (early["Level"] == "Insufficient history").all()


def test_score_latest_ranks_every_vessel(fact):
    latest = ew.score_latest(fact)
    assert len(latest) == 14
    assert latest["Period"].nunique() == 1
