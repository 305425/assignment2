# Early-warning prototype (D5)

A monthly rule that flags vessels whose cost control is likely to stay poor over the next quarter. It was tested month by month on history it had not seen. Code is in `analysis/early_warning.py`; results are in the `EW_*` sheets of `GNMTC_Vessel_Cost_Analysis.xlsx`.

## What it does

At each month-end, every vessel gets one of three levels, using only data up to and including that month.

| Level | Trigger | Action |
|---|---|---|
| **Escalate** | Three-month variance above 5% of budget, **or** more than $10,000 of non-budgeted spend in the last three months | Vessel manager gives a written explanation within the month. A second consecutive Escalate goes to management review. |
| **Watch** | Three-month variance above 3%, **or** any non-budgeted spend in the last three months, **or** one cost category over 10% in four of the last six months | Reviewed in the monthly pack; no explanation required. The category trigger names the category. |
| None | None of the above | — |

A vessel needs six months of history before it is scored, so the first scored month is June 2024. This is a limit of the design, not a finding: the two main triggers need only three months. Scored from three months, B78, E48, K56 and M75 would have escalated in March 2024 and H72 in April 2024. N77, which never escalated later, would also have escalated in March 2024, which is the cost of the shorter window.

A separate **fleet alert** compares the fleet's repairs and safety variance rates each quarter against their 2024 rates (repairs +2.7%, safety +0.1%). It fires only when a quarter's rate is more than 2 percentage points above the 2024 rate. Without that margin, the +0.1% safety baseline made any positive quarter an alert. Safety fired in every quarter from 2025 Q1 to 2026 Q2 and in July 2026 (+13.5%). Repairs fired in every quarter in that span except 2025 Q4 (+3.5%) and July 2026 (+1.4%).

## Why a rule and not a model

- **The signal is simple.** Two inputs carry it: the recent variance rate, and whether non-budgeted spend is appearing. Both are already in the monthly pack, and a manager can check either by hand.
- **There is very little history.** Fourteen vessels over 31 months gives 322 vessel-months with a complete outcome, and only 56 in the held-out test.
- **The model did worse.** A logistic regression on seven features did worse than the rule on held-out 2026 months (table below), and its coefficients were unstable. For example, the technical-category rate got a negative weight.
- **The brief scores defensibility.** It says a complex solution scores poorly if it cannot be explained.

## What it predicts, and how that was tested

A vessel-month is a **bad outcome** if, over the following three months, total variance is above 5% of budget, or non-budgeted spend is above $10,000. Every feature for month *t* uses months up to *t*. The outcome uses months *t*+1 to *t*+3 only. The last three months (May to July 2026) are scored but cannot be evaluated.

Automated tests confirm there is no look-ahead. Features and levels for any month are identical whether or not later months exist in the data, the outcome window starts the month after *t*, and unscored months stay unscored (`tests/test_early_warning.py`).

**The rule was changed once, before the 2026 test.** The planned rule also escalated on the category trigger. On June 2024 to September 2025, that version flagged 108 vessel-months: 55% were right, and 32% of good vessel-months were wrongly flagged. Well-controlled A17 was escalated for 7 months. Monthly category variances are noisy: 30% of all vessel-category-months are more than 10% over budget. The trigger was therefore moved to Watch. The choice was made on the tuning columns of `EW_Rule_Selection`. The 2026 columns are shown there for transparency and were not used to choose.

| Candidate escalation rule | Tuning: share of flags correct | Tuning: share of bad outcomes caught | Tuning: false alarms |
|---|---:|---:|---:|
| Planned: variance, category, or non-budgeted | 55% | 83% | 32% |
| **Selected: variance or non-budgeted > $10k** | **78%** | **75%** | **10%** |
| Category trigger needs 5 of 6 months | 68% | 79% | 17% |
| Variance must also hold over 6 months | 80% | 72% | 9% |
| Any non-budgeted spend | 74% | 90% | 14% |
| Baseline: last month alone > 5% | 55% | 58% | 22% |

In the tables, **precision** is the share of flags that were right, **recall** is the share of bad outcomes that were flagged, and **false alarms** is the share of good vessel-months that were flagged.

## Results

**Escalate level against the bad-outcome definition:**

| Method | Period | Flags | Precision | Recall | False alarms |
|---|---|---:|---:|---:|---:|
| Selected rule | Jun 2024 to Apr 2026 (322 vessel-months) | 106 | 76% | 73% | 12% |
| Selected rule | 2025 | 60 | 82% | 78% | 10% |
| Selected rule | **Jan to Apr 2026, not used for rule selection** (56) | 21 | **76%** (16 of 21) | **64%** (16 of 25) | **16%** |
| Planned rule | Jan to Apr 2026 | 37 | 62% | 92% | 45% |
| Last month > 5% | Jan to Apr 2026 | 20 | 60% | 48% | 26% |
| Logistic regression | Jan to Apr 2026 | 20 | 65% | 52% | 23% |

Watch or Escalate together catch 95% of bad outcomes overall, but with a 45% false-alarm rate. That is why Watch needs no explanation from the vessel manager.

**How much weight these results bear.** Four points limit what the table shows.

- **Base rate.** 34% of all evaluated vessel-months, and 45% of the 2026 test months, had a bad outcome. A flag that is right 76% of the time is better than chance, but by less than the raw figure suggests.
- **Few independent cases.** Five persistent vessels supply almost all the bad outcomes. Resampling whole vessels, 95% ranges for the selected rule on 2026 are precision 40% to 100% and recall 33% to 86%. The ranges for the baseline (28% to 86% precision, 31% to 62% recall) and logistic regression (21% to 100%, 17% to 82%) overlap them. The data supports "no worse than the baselines and simpler", not "better".
- **Recall trade-off.** The selected rule misses 9 of 25 bad outcomes in 2026. The planned rule on the same months catches 92%, at a 45% false-alarm rate. Management is choosing fewer false alarms over fewer misses. Watch or Escalate together is the wider net.
- **Vessel level.** Across all months, 11 of 14 vessels had at least one bad outcome window. 10 were escalated at some point; G17 (one bad window) never was. Many of those escalations are single months on vessels that were otherwise fine (F86, J18). The rule's clear value is on the five persistent vessels. On drifting vessels it is late (below).

The logistic regression scores 87% precision and 76% recall on 2025, but 2025 is where its threshold was chosen, so that result is not a fair test.

**Sensitivity check.** Non-budgeted spend is part of both the trigger and the outcome, which flatters the rule. Against a variance-only outcome (next three months above 5%), the selected rule still beats the baseline: precision 60% against 48%, and recall 69% against 55%. On 2026 it scores 62% and 59%, against 45% and 41%.

**By vessel:**

- **Escalated from June 2024:** E48, H72, B78, K56 and M75 (the five vessels with non-budgeted spend), each in the first month the rule could score.
  - E48 stayed escalated in all 26 scored months, B78 in 25, H72 in 22, K56 in 20, M75 in 15.
  - M75's 2024 variance was only +0.3%. The rule caught it through its 2024 non-budgeted spend, not its variance.
- **Rarely or never escalated:** A17, D49 and N77 were never escalated. F86 was escalated for 2 months, J18 and G17 for 1 each.
- **Flagged late (the cases where an early warning would have mattered most):** for vessels that drift over budget without non-budgeted spend, the rule is about three months late.
  - L96's first bad outcome window began in December 2024, and it was first escalated in March 2025.
  - I27's began in August 2025, and it was first escalated in November 2025.
  - The rule waits for three months of variance. It cannot see a first-time problem before it shows up in the ledger.
- **Workload:** an average of 4.8 vessels escalated per month (range 2 to 8) and 4.0 on Watch. That is manageable for a 14-vessel fleet. Most escalations are the same five vessels month after month, which is the point of the second-consecutive-month escalation step.

## Latest month (July 2026)

| Vessel | Level | Why |
|---|---|---|
| H72 | Escalate | Three-month variance +16.1%; $11,276 non-budgeted |
| E48 | Escalate | +13.7%; $24,660 non-budgeted |
| B78 | Escalate | +7.6%; $21,617 non-budgeted |
| M75 | Escalate | +6.2% |
| K56 | Escalate | +5.5%; $39,188 non-budgeted |
| F86 | Watch | Three-month variance +4.1% |
| J18 | Watch | Safety & Compliance over 10% in 4 of the last 6 months |
| I27 | Watch | Other Operating Cost over 10% in 4 of the last 6 months |

The other six vessels have no flag. Run `score_latest()` each month-end to regenerate this list.

## Limits

- **The data is synthetic.** These results show the method works on this file. They are not a performance claim for a real fleet.
- **The test is small and not independent.** It covers 56 vessel-months. Consecutive months share two of their three outcome months, so the precision and recall figures are less certain than their counts suggest.
- **Thresholds were set with sight of the whole dataset.** The 5%, 3% and $10,000 values were chosen while exploring all 31 months. Only the choice between candidate rules was confined to the tuning period, and the 2026 columns were visible when the candidates were compared. "Held out" therefore means only "not used to choose between candidate rules".
- **It repeats what is already visible.** The rule mostly confirms persistent problems. It is weak on first-time drift, and it cannot predict a breakdown, a survey finding or a crew change before the cost lands.
- **The non-budgeted trigger depends on an unconfirmed definition.** It relies on the `Budget_Status` flag, whose definition is not documented in the source.

## How management would use it

1. At month-end close, run `py -3 -m analysis.run_all` and open the `EW_Latest` sheet.
2. Each Escalate goes to the vessel manager for a written explanation that names the cost lines, using `Hotspots` and `Hotspot_Themes`.
3. A second consecutive Escalate, or any fleet alert, goes to the monthly management review with a proposed action.
4. Every quarter, check `EW_Backtest` again as new months arrive, and revisit the thresholds only on months the rule has not been tuned on.
