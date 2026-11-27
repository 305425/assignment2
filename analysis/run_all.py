"""Rebuild every output from the source workbook: py -3 -m analysis.run_all"""
import json
import sys

if __package__ in (None, ""):
    import pathlib, runpy
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    runpy.run_module("analysis.run_all", run_name="__main__")
    sys.exit()

from . import charts, config, dashboard, early_warning, findings, registers
from .build_dataset import assert_identity, build_fact, fleet_totals
from .build_workbook import build_workbook
from .load import load_source
from .validate import assert_valid, checks_frame, run_checks


def main() -> dict:
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    src = load_source()
    checks = run_checks(src)
    assert_valid(checks)

    fact = build_fact(src)
    assert_identity(fact)
    fact.to_csv(config.OUTPUT_DIR / "analytical_dataset.csv", index=False)

    tables = findings.build_all(fact, src.transactions)
    bt = early_warning.backtest(fact)
    latest = early_warning.score_latest(fact)
    evidence = registers.evidence_register(tables, bt, fact)
    controls = registers.control_register()
    assumptions = registers.assumptions()
    chart_paths = charts.build_all(fact, tables, bt)

    workbook = config.OUTPUT_DIR / "GNMTC_Vessel_Cost_Analysis.xlsx"
    build_workbook(workbook, src.snapshot, checks_frame(checks), fact, tables, bt,
                   evidence, controls, assumptions, latest)

    dashboard.build_dashboard(
        config.OUTPUT_DIR / "Dashboard.html",
        dashboard.build_payload(fact, tables, bt, latest, evidence, controls, src.snapshot))

    summary = {
        "snapshot": src.snapshot,
        "totals": {k: round(float(v), 2) for k, v in fleet_totals(fact).items()},
        "checks": {c.name: c.status for c in checks},
        "workbook": str(workbook),
        "charts": [p.name for p in chart_paths],
    }
    (config.OUTPUT_DIR / "build_summary.json").write_text(json.dumps(summary, indent=2))
    figures = registers.summary_figures(tables, bt, latest)
    (config.OUTPUT_DIR / "summary_figures.json").write_text(json.dumps(figures, indent=2))
    return {"src": src, "fact": fact, "tables": tables, "bt": bt, "latest": latest,
            "evidence": evidence, "controls": controls, "summary": summary}


if __name__ == "__main__":
    out = main()
    s = out["summary"]
    print(f"Built {s['workbook']}")
    print("Totals:", s["totals"])
    print("Checks:", {k: v for k, v in s["checks"].items() if v != "Pass"} or "all pass")
