# GNMTC vessel cost control: analysis and early-warning prototype

Independent review of vessel cost performance for a ship-management fleet (14 vessels, January 2024 to July 2026). It answers the brief's question: what should management have known earlier, and what should change on future vessels. The data is synthetic.

## Where to start

| Read this | For |
|---|---|
| `outputs/Management_Summary.pdf` | Two-page summary of findings, financial impact and recommendations |
| `outputs/Dashboard.html` | Interactive dashboard of all findings (open in a browser) |
| `outputs/GNMTC_Vessel_Cost_Analysis.xlsx` | Analysis workbook: dataset, reconciliation, findings, early-warning results, evidence and control registers |
| `outputs/Evidence_and_Limitations.md` | Evidence register, charts, limitations, open questions |
| `outputs/Early_Warning_Prototype.md` | Prototype logic, backtest results, limits, how management would use it |
| `GNMTC_Data_Quality_Assessment.xlsx` | Source validation and trust ratings |
| `vessel-cost-analysis.md` | Exploratory analysis notes |

## Brief deliverables

| Brief deliverable | File |
|---|---|
| Working analysis file or analytical dataset | `outputs/GNMTC_Vessel_Cost_Analysis.xlsx` (sheet `Fact_Monthly`), `outputs/analytical_dataset.csv` |
| Management summary | `outputs/Management_Summary.docx` and `.pdf` |
| Evidence, limitations, unresolved issues | `outputs/Evidence_and_Limitations.md`, workbook sheets `Evidence_Register` and `Reconciliation` |
| Recommendations and controls | Workbook sheet `Control_Register`, summary section on recommendations |
| Early-warning prototype | `analysis/early_warning.py`, `outputs/Early_Warning_Prototype.md`, `outputs/Dashboard.html` (Early warning tab) |

## Replicate the prototype

### Requirements

- Python 3.11 or later (built on 3.13). On Windows use `py -3`; elsewhere use `python3`.
- Node.js 18 or later, only for the Word summary.
- Microsoft Excel and Word on Windows, only for recalculating the workbook and exporting the PDF. Everything else runs without them.

### Steps

1. Install the Python packages. Versions used are in `requirements.txt`.

   ```
   py -3 -m pip install -r requirements.txt
   ```

2. Keep the source workbook in this folder under its original name, `Synthetic_GNMTC_Vessel_Cost_Risk_Data (2).xlsx`. It is read-only input.

3. Rebuild the dataset, findings, early-warning backtest, charts, workbook and dashboard in one run.

   ```
   py -3 -m analysis.run_all
   ```

   The run stops with an error if a validation check fails. Three checks are known issues and do not stop it: the off-budget column does not match non-budgeted spend, K56's issue counts conflict, and four vessels have no handover record.

4. Run the tests: reconciliation to the source, and no look-ahead in the early-warning features.

   ```
   py -3 -m pytest tests -q
   ```

   Expected: 16 passed.

5. Open `outputs/Dashboard.html` in a browser. To open a tab directly, add its name, for example `Dashboard.html#Early%20warning`.

6. Optional, Windows with Office only. Recalculate the workbook formulas and check them.

   ```
   powershell -File analysis\recalc_excel.ps1 -Path outputs\GNMTC_Vessel_Cost_Analysis.xlsx
   py -3 -m analysis.verify_workbook
   ```

   Expected: 323 formulas, 0 errors, 0 mismatches with Python.

7. Optional. Rebuild the management summary.

   ```
   cd docgen
   npm install
   cd ..
   node docgen/build_summary.js
   powershell -File analysis\export_pdf.ps1 -Path outputs\Management_Summary.docx
   ```

### Run the early-warning rule on its own

```python
from analysis.load import load_source
from analysis.build_dataset import build_fact
from analysis import early_warning

fact = build_fact(load_source())
print(early_warning.score_latest(fact))     # latest month: Escalate / Watch / None per vessel
```

For a new month, add the rows to the source workbook and run it again.

### Settings

All thresholds are in `analysis/config.py`: the early-warning limits (3% watch, 5% escalate, $10,000 non-budgeted), the three-month outcome window, the train and tune periods, the fleet-alert margin and the cost bands. The workbook sheet `Assumptions` lists each with its reason.

## How the work is organised

```
analysis/
  config.py          settings and thresholds
  load.py            reads the four source sheets
  validate.py        reconciliation checks; stops the run on failure
  build_dataset.py   analytical dataset, one row per vessel, month and category
  findings.py        bridge, vessel, category, hotspot, handover tables
  early_warning.py   rule, walk-forward backtest, baselines, score_latest()
  registers.py       evidence register, control register, assumptions
  charts.py          PNG charts
  build_workbook.py  analysis workbook (summary sheets are Excel formulas)
  verify_workbook.py checks workbook formulas against Python
  dashboard.py       self-contained interactive dashboard
  run_all.py         one command that rebuilds everything
tests/               reconciliation and no-look-ahead tests
docgen/              Word management summary (Node, docx package)
outputs/             generated deliverables
```

## Method in brief

- **Compute from source.** Every figure traces to the source workbook through code or an Excel formula. Existing totals and labels were not trusted.
- **Variance is split three ways.** Variance = non-budgeted spend + (budgeted lines minus budget). The off-budget column is not used as unbudgeted cost because it does not reconcile.
- **Early-warning rule.** At each month-end, a vessel is escalated if its three-month variance is above 5% of budget, or it has more than $10,000 of non-budgeted spend in three months. Watch is a lower tier. It is tested month by month on data it had not seen, against a last-month baseline and a logistic regression.
- **Claims are labelled** fact, interpretation or open in the evidence register.

## Limits

- The data is synthetic and covers 14 vessels, with 2026 ending in July.
- The early-warning test is small (56 vessel-months), mostly from five persistent vessels. Differences from the baselines are within chance.
- The thresholds were chosen with sight of the whole history.
- The data cannot show why repairs and safety costs rose. It has no maintenance, defect or purchase-order records.

See `outputs/Evidence_and_Limitations.md` for the full list and the questions for the data owner.

## Deploy the dashboard to Firebase Hosting

The dashboard is one static file, so any static host works. For Firebase:

```
npm install -g firebase-tools
firebase login
firebase use --add            # pick or create a Firebase project
copy outputs\Dashboard.html public\index.html
firebase deploy --only hosting
```

The command prints the hosting URL (`https://<project-id>.web.app`). `firebase.json` serves only the `public/` folder, so the workbook and source data are not published. The page is public to anyone with the link. The data is synthetic.
