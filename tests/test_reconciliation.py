import numpy as np
import pytest

from analysis import findings
from analysis.build_dataset import assert_identity, fleet_totals
from analysis.validate import assert_valid, run_checks


def test_source_checks_have_no_failures(source):
    checks = run_checks(source)
    assert_valid(checks)
    known = {c.name for c in checks if c.status == "Known issue"}
    assert known == {
        "Off_Budget_USD equals non-budgeted transaction spend",
        "Overdue issues do not exceed open issues",
        "Every vessel has a handover record",
    }


def test_dataset_grain(fact):
    assert len(fact) == 14 * 31 * 8
    assert not fact.duplicated(["Vessel_ID", "Period", "Cost_Category"]).any()


def test_fleet_totals_reproduce_source(source, fact):
    totals = fleet_totals(fact)
    assert totals["budget"] == pytest.approx(source.monthly["Budget_USD"].sum(), abs=0.01)
    assert totals["actual"] == pytest.approx(source.monthly["Actual_USD"].sum(), abs=0.01)
    assert totals["variance"] == pytest.approx(585_991.84, abs=0.01)
    nb = source.transactions.loc[
        source.transactions["Budget_Status"] == "Non-Budgeted", "Amount_USD"].sum()
    assert totals["nonbudgeted"] == pytest.approx(nb, abs=0.01)
    assert totals["off_budget_source"] == pytest.approx(106_513.80, abs=0.01)


def test_variance_identity_holds_per_row(fact):
    assert_identity(fact)


def test_transactions_roll_up_within_two_cents(fact):
    assert fact["Txn_vs_Actual_Diff_USD"].abs().max() <= 0.02 + 1e-9


def test_missing_handover_rows_are_not_zero(fact):
    missing = fact.loc[~fact["Has_Handover_Record"], "Vessel_ID"].unique()
    assert set(missing) == {"V1002", "V1007", "V1012", "V1013"}
    assert fact.loc[~fact["Has_Handover_Record"], "Deferred_Exposure_USD"].isna().all()


def test_bridge_sums_to_fleet(fact):
    bridge = findings.fleet_bridge(fact).set_index("Period")
    years = bridge.drop(index="All")
    assert years["Variance_USD"].sum() == pytest.approx(bridge.loc["All", "Variance_USD"])
    assert np.isclose(bridge.loc["All", "Variance_USD"],
                      bridge.loc["All", "NonBudgeted_Spend_USD"] + bridge.loc["All", "Budgeted_Gap_USD"])


def test_scorecard_covers_every_vessel(fact):
    sc = findings.vessel_scorecard(fact)
    assert len(sc) == 14
    assert sc["Variance_USD"].sum() == pytest.approx(fact["Variance_USD"].sum())
