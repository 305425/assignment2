# Vessel cost control: entities, checks, and findings

Synthetic fleet data for a ship-management cost review, January 2024 through July 2026. Figures below are calculated from the workbook. They describe this dataset only. The file is artificial and is not a record of a real fleet.

The management question is what should have been visible earlier, and what should change before taking on another similar vessel.

## 1. Entities and how they connect

Five tables. Four of them carry data.

| Entity | Grain | Rows | Role |
|---|---|---|---|
| Vessel_Master | One row per vessel | 14 | Identity: type, age, DWT, management status |
| Monthly_Budget_Actual | Vessel × month × cost category | 3,472 | Budget, actual, variance, and an off-budget amount |
| Cost_Transactions | One cost event | 10,361 | What was bought, urgency, and whether it was budgeted |
| Handover_Deferred_Risk | One row per listed vessel | 10 | Open and overdue issues, estimated deferred exposure, risk label, owner |
| README / Data_Dictionary | Notes | — | Purpose and the warning that values are synthetic |

How they join:

- **Vessel_Master → Monthly_Budget_Actual** and **Vessel_Master → Cost_Transactions** are one-to-many on `Vessel_ID`. All 14 vessels appear in both cost tables. Names match the master on every row.
- **Cost_Transactions → Monthly_Budget_Actual** rolls up on `Vessel_ID` + calendar month + `Cost_Category`. All 3,472 monthly actuals have a matching transaction total. The largest cell difference is $0.02, from rounding. Transaction lines are the detail behind actual spend, not a second ledger.
- **Vessel_Master → Handover_Deferred_Risk** is a partial one-to-one on `Vessel_ID`. Ten vessels have a handover row. Four do not: Vessel-B78, Vessel-G17, Vessel-L96, Vessel-M75.
- Management status and the handover sheet are different lists. Four vessels are marked **Handover Review** (D49, F86, H72, I27). The handover sheet also includes six vessels marked **Active**, and it omits no Handover Review vessel. It does omit B78 and M75, both of which have material cost issues (section 5).

Shared dimensions:

- Eight cost categories on both cost tables: Crew Wages, Repairs & Maintenance, Spares, Stores, Crew Travel, Logistics & Freight, Safety & Compliance, Other Operating Cost.
- Twenty-five description themes sit under those categories (for example main-engine spares, valve overhaul, relief crew wages, urgent air freight). Themes have no budget of their own. They explain composition of spend, not variance by themselves.
- Period coverage is complete: 14 vessels × 31 months × 8 categories = 3,472. 2024 and 2025 are full years. 2026 stops at July (last transaction date 27 July 2026). There are no duplicate monthly keys, no nulls, no negative amounts, and no zero budgets.
- `Variance_USD` equals actual minus budget on every row. `Variance_Pct` equals that difference divided by budget.

```text
Vessel_Master
    |  Vessel_ID (14 = 14)
    +--> Monthly_Budget_Actual  <--sum of Amount_USD--  Cost_Transactions
    |         vessel × month × category                         |
    |         Budget, Actual, Variance, Off_Budget              | Budget_Status
    |                                                           | Urgency, Description_Theme
    +--> Handover_Deferred_Risk (10 of 14)
              Open_Issues, Overdue_Issues,
              Estimated_Deferred_Exposure_USD,
              Handover_Risk, Primary_Owner
```

## 2. What can be trusted, and what cannot

Trust the monthly budget, the monthly actual, and the transaction amounts. They agree with each other, and the variance arithmetic is correct.

Do not treat these three fields as the same fact:

| Field | What it actually is | What it is easy to assume |
|---|---|---|
| `Variance_USD` | Actual minus budget. Fleet total **+$585,992** on a **$24,765,499** budget (**+2.4%**). | A full picture of control. It nets underspend against overspend, including unbudgeted lines. |
| `Budget_Status = Non-Budgeted` | 228 transactions, **$711,719**, all inside the actuals, on five vessels only. | A small exception. It is larger than the fleet variance. |
| `Off_Budget_USD` | **$106,514** on the same 228 vessel-month-category cells as the non-budgeted transactions. Amounts do not match. Median off-budget value is about 16% of the non-budgeted dollars in that cell, and about 7% of that cell’s actual. 86 of the 228 cells are still under budget. | The unbudgeted spend. It is not. |

The identity that matters:

**fleet variance = non-budgeted spend + (budgeted spend − budget)**

**$585,992 = $711,719 + (−$125,727)**

Budgeted transactions, taken together, came in **$125,727 under** budget. The non-budgeted spend on five vessels is larger than the whole fleet overrun. That is an identity, not proof of cause: the data cannot show whether this spend was extra, or budgeted work coded as non-budgeted (crew wages, where $181,800 of non-budgeted spend sits against $178,873 of budgeted underspend, is the clearest case). A budget-versus-actual report shows a 2.4% miss. The transaction flag shows a $712k block of spend that was never in the budget, partly masked by underspend on budgeted lines.

`Handover_Risk` does not rank vessels by deferred dollars or by cost variance (section 6). `Management_Status` does not rank them by cost outcome either. Handover Review vessels as a group are **+2.0%** versus budget. Active vessels are **+2.5%**.

Age versus variance percent is weak (correlation about 0.18). DWT versus variance percent is negative (about −0.70) because two smaller vessels, E48 and H72, dominate the overrun. With 14 vessels that is not a rule to manage by. Vessel type averages have the same problem: offshore support is the worst type rate only because E48 is in it; the other offshore vessel, J18, is flat.

## 3. Fleet result over time

| Year | Months | Budget | Variance | Variance % | Non-budgeted | Budgeted spend vs budget |
|---|---:|---:|---:|---:|---:|---:|
| 2024 | 12 | $9,609,283 | +$157,326 | +1.6% | $244,067 | −$86,741 |
| 2025 | 12 | $9,606,505 | +$252,465 | +2.6% | $250,603 | +$1,863 |
| 2026 | 7 | $5,549,711 | +$176,201 | +3.2% | $217,049 | −$40,848 |
| All | 31 | $24,765,499 | +$585,992 | +2.4% | $711,719 | −$125,727 |

The monthly overrun pace rose from about **$13,100** in 2024 to **$21,000** in 2025 and **$25,200** in 2026. Comparing full years with a seven-month year on dollar totals understates 2026. On rate, 2026 is the worst slice so far.

By category, net variance:

| Category | Budget | Variance | Variance % | Non-budgeted | Budgeted spend vs budget |
|---|---:|---:|---:|---:|---:|
| Repairs & Maintenance | $3,955,097 | +$186,285 | +4.7% | $106,494 | +$79,791 |
| Spares | $3,958,441 | +$136,809 | +3.5% | $124,403 | +$12,407 |
| Logistics & Freight | $1,932,240 | +$89,324 | +4.6% | $65,530 | +$23,794 |
| Safety & Compliance | $1,936,453 | +$85,234 | +4.4% | $61,521 | +$23,713 |
| Crew Travel | $1,949,360 | +$41,755 | +2.1% | $63,535 | −$21,781 |
| Other Operating Cost | $1,946,657 | +$24,041 | +1.2% | $47,276 | −$23,235 |
| Stores | $2,615,245 | +$19,616 | +0.8% | $61,159 | −$41,543 |
| Crew Wages | $6,472,005 | +$2,927 | +0.0% | $181,800 | −$178,873 |

Two different mechanisms:

- **Repairs, spares, logistics, and safety** are over budget on the budgeted lines themselves, and they also carry non-budgeted spend. Repairs are the largest dollar miss. Safety is the sharpest deterioration (below).
- **Crew wages** look controlled (+0.05%) and are the largest budget line, about 26% of the fleet budget. That result is an offset: **$181,800** non-budgeted wages against **$178,873** of budgeted wages under the budget. Stores, travel, and other operating cost have the same shape at a smaller scale.

Urgent transactions are 573 lines and **$1,043,294** (4.1% of spend). 513 of those lines are logistics (local delivery, sea freight, urgent air freight), and urgent freight is 42% of logistics spend. Urgency here is mostly a freight label. It clusters on the same five vessels as the non-budgeted spend, so it is a supporting flag, not a separate problem.

## 4. Where the overrun sits

Eleven vessels are over budget in total. Three are under: A17 (−$17,577), F86 (−$15,668), G17 (−$7,172).

Four vessels produce **78%** of the net fleet variance. Five vessels — the only ones with any non-budgeted spend — produce **86%**.

| Vessel | Status | Type | Variance | Var % | Months over budget | Non-budgeted | Budgeted spend vs budget |
|---|---|---|---:|---:|---:|---:|---:|
| E48 | Active | Offshore support, age 19 | +$128,817 | +8.8% | 29 of 31 | $155,533 | −$26,716 |
| H72 | Handover Review | Chemical tanker, age 11 | +$123,748 | +7.6% | 28 of 31 | $119,669 | +$4,079 |
| B78 | Active | Container, age 18 | +$116,040 | +5.9% | 27 of 31 | $138,449 | −$22,409 |
| K56 | Active | Bulk carrier, age 18 | +$86,887 | +4.2% | 21 of 31 | $185,428 | −$98,540 |
| M75 | Active | Chemical tanker, age 11 | +$50,442 | +4.1% | 21 of 31 | $112,640 | −$62,198 |
| L96 | Active | Container, age 15 | +$52,125 | +2.2% | 18 of 31 | $0 | +$52,125 |
| I27 | Handover Review | Product tanker, age 8 | +$24,451 | +1.4% | 18 of 31 | $0 | +$24,451 |
| N77 | Active | Product tanker, age 18 | +$18,519 | +1.2% | 16 of 31 | $0 | +$18,519 |
| C68 | Active | Chemical tanker, age 13 | +$14,448 | +0.6% | 17 of 31 | $0 | +$14,448 |
| D49 | Handover Review | Product tanker, age 7 | +$10,017 | +0.6% | 19 of 31 | $0 | +$10,017 |
| J18 | Active | Offshore support, age 20 | +$914 | +0.1% | 16 of 31 | $0 | +$914 |
| G17 | Active | Container, age 13 | −$7,172 | −0.5% | 12 of 31 | $0 | −$7,172 |
| F86 | Handover Review | Bulk carrier, age 12 | −$15,668 | −0.7% | 13 of 31 | $0 | −$15,668 |
| A17 | Active | Bulk carrier, age 17 | −$17,577 | −1.4% | 10 of 31 | $0 | −$17,577 |

Reading the top of the table:

- **E48, B78, K56, and M75** are over budget only because non-budgeted spend exceeds an underspend on budgeted lines. K56 is the clearest case: budgeted spend is **$98,540 under** budget, non-budgeted spend is **$185,428**, and the published overrun is **$86,887**. A variance review of K56 understates the control failure.
- **H72** is the one large miss that is over on budgeted lines as well as on non-budgeted spend. It is also in Handover Review.
- **L96** has no non-budgeted spend. Its +$52,125 is ordinary budget drift, mostly crew wages (+$33,094). That is a different problem from the five-vessel leak.
- **A17 and F86** are the cost-control examples. A17’s result is crew wages **$23,965 under** budget. F86 is under on repairs (−$12,814) and spares (−$12,025). F86 is in Handover Review and still has a large deferred-work balance (section 6), so a good cost variance is not a clean handover.

Largest vessel-category misses over the full window:

| Vessel | Category | Variance | Variance % | How often |
|---|---|---:|---:|---|
| K56 | Repairs & Maintenance | +$39,960 | +12.2% | Repeated; electrical repair and hydraulic pump repair dominate the spend |
| B78 | Repairs & Maintenance | +$39,251 | +12.5% | Repeated; steel work is the largest theme |
| H72 | Safety & Compliance | +$37,395 | +29.5% | Over in 24 of 31 months; lifesaving appliances, survey preparation, fire safety |
| E48 | Crew Travel | +$35,511 | +30.8% | Over in 29 of 31 months; crew-change and emergency travel, both budgeted and not |
| L96 | Crew Wages | +$33,094 | +5.2% | Budgeted drift, no non-budgeted lines |
| K56 | Spares | +$30,600 | +9.4% | Repeated with the repairs miss |
| H72 | Repairs & Maintenance | +$27,313 | +10.7% | With spares +$25,571 |

The favourable crew-wage gaps on I27 (−$29,385) and A17 (−$23,965) are the main savings in the file. They are single-category results, not evidence of a fleet wage-control system. I27’s wage saving is also what keeps a Handover Review vessel looking close to budget.

## 5. What was already visible, and what got worse

The four worst vessels were already over budget in the first half of 2024, and the rate rose after that.

| Vessel | H1 2024 | Full 2024 | 2025 | 2026 (7 months) |
|---|---:|---:|---:|---:|
| H72 | +7.2% | +4.2% | +8.9% | +11.5% |
| E48 | +6.3% | +7.7% | +9.3% | +9.7% |
| B78 | +3.1% | +4.6% | +6.4% | +7.4% |
| K56 | +3.4% | +1.7% | +6.8% | +4.3% |
| M75 | +1.3% | +0.3% | +6.9% | +5.9% |

H72 and E48 were the two worst vessels in the first six months. Waiting for a year-end pack was not required to see them. Both then stayed over in about nine months out of ten, so the pattern is repeated, not a dry-dock spike or a single invoice.

Category rates moved the same way:

- Repairs variance percent: **+2.7%** in 2024, **+5.3%** in 2025, **+7.1%** in 2026.
- Safety: **+0.1%** in 2024, **+6.0%** in 2025, **+9.3%** in 2026. Safety in 2026 Q2 was +10%, and July 2026 alone was +13%.
- Spares stayed in a +2% to +4% band, with a worse 2025 (+4.2%).

2026 Q3 in this file is July only. Repairs in that single month were close to budget (+1.4%). That is one month, after two quarters at +8.4% and +7.6%. It is not a turnaround.

M75 is the case a variance-only watchlist misses. Its 2024 variance was nearly on budget (+0.3%), and its rate only jumped in 2025 (+6.9%). It already had non-budgeted spend in 2024, so a check on the transaction flag would have caught it in June 2024 (see `outputs/Early_Warning_Prototype.md`). K56’s published variance also jumped in 2025, while its non-budgeted total is the largest in the fleet across the whole window.

## 6. Handover risk is a different question from cost control

The handover sheet lists **91 open issues**, **25 overdue**, and **$1,336,384** of estimated deferred exposure. As recorded, it is a balance of outstanding work, so it is not compared with the 31-month cost overrun. It is not validated: the sheet gives no estimation method and no as-of date. Treat it as a recorded estimate, and do not add it to the overrun or net it against it.

The issue counts also contain a contradiction. K56 shows 5 overdue issues and only 4 open ones, which is impossible if overdue issues are a subset of open issues. K56’s counts below are shown as recorded and should not be used to rank it.

The risk label does not follow the money.

| Vessel | Risk label | Status | Deferred exposure | Overdue | Cost variance | Non-budgeted |
|---|---|---|---:|---:|---:|---:|
| N77 | High | Active | $167,023 | 1 | +$18,519 | $0 |
| H72 | High | Handover Review | $123,954 | 2 | +$123,748 | $119,669 |
| E48 | High | Active | $74,399 | 4 | +$128,817 | $155,533 |
| I27 | Medium | Handover Review | $169,706 | 1 | +$24,451 | $0 |
| D49 | Low | Handover Review | $168,702 | 4 | +$10,017 | $0 |
| F86 | Medium | Handover Review | $159,315 | 1 | −$15,668 | $0 |
| C68 | Medium | Active | $159,119 | 4 | +$14,448 | $0 |
| J18 | Medium | Active | $130,522 | 0 | +$914 | $0 |
| K56 | Low | Active | $129,845 | 5 | +$86,887 | $185,428 |
| A17 | Medium | Active | $53,799 | 3 | −$17,577 | $0 |

Facts this table supports:

- Correlation between deferred exposure and cost variance is about **−0.29**. High deferred dollars and a bad cost trend are not the same vessels.
- **K56** is labelled Low and is Active, with the most non-budgeted spend ($185k). Its recorded 5 overdue issues exceed its 4 open issues, so its issue counts are unreliable.
- **D49** is labelled Low while in Handover Review, with $169k deferred and 4 overdue issues, and only a +0.6% cost variance.
- **N77** is High on a $167k deferred balance and a +1.2% cost variance.
- **E48** is High with the smallest deferred balance in the High group ($74k) and the worst cost record.
- **B78** (+$116k variance, $138k non-budgeted) and **M75** ($113k non-budgeted) have **no handover row at all**. Any review that starts from this sheet will not see them.
- Primary owner is a label only. Operations (3 vessels), Marine (3), Procurement (2), and Technical (2) do not line up with who has the cost problem. H72 and E48 are both Operations. K56, the largest unbudgeted case, is Procurement.

Open-issue counts also fail as a severity rank. C68 has 16 open issues and a +0.6% cost variance. I27 has 3 open issues and the largest deferred balance.

## 7. What the data does not support

- A cause for the repairs and safety drift. There is no planned-maintenance history, defect list, dry-dock flag, equipment hierarchy, or purchase-order trail. Theme names (valve overhaul, steel work, survey preparation) describe the invoice, not why the work happened or whether it was deferred from an earlier period.
- A claim that age, DWT, or vessel type causes the overrun. The rates are vessel-specific.
- Using `Off_Budget_USD` as unbudgeted cost, or using `Handover_Risk` as a cost-control score.
- A production early-warning model. The history is synthetic, 2026 is partial, and the useful signal is a repeated rate on a handful of vessels, which a simple watch rule already shows. In the backtest, a logistic regression on the same inputs did worse than the simple rule on held-out 2026 months (`outputs/Early_Warning_Prototype.md`).
- Treating crew wages as “under control” because the category nets to zero.

## 8. What management can act on

These follow from the figures above.

1. **Review the five unbudgeted vessels before any handover sign-off**, including B78 and M75, which are missing from the handover sheet. Report non-budgeted spend beside variance. For K56, M75, E48, and B78 the variance is the remainder after budgeted underspend absorbed part of the leak.
2. **Put H72 and E48 on a monthly escalation now.** Both were the worst vessels in H1 2024, both are still worsening, and both combine a bad run rate with a High risk label. H72 is the vessel actually in Handover Review that fails on cost. The specific lines are H72 safety (+29%), repairs, and spares, and E48 crew travel (+31%) plus repairs, spares, and logistics.
3. **Separate deferred exposure from cost performance in the handover pack.** Recorded deferred work is $1.34 million, but that figure has no method or as-of date, so it needs validating before it is relied on. It is a balance of outstanding work, not a cost flow, so it is not compared with the overrun. D49, I27, F86, and N77 are handover problems because of unresolved exposure, not because of a large budget miss. F86 shows that an underspend can sit next to $159k of deferred work.
4. **Watch repairs and safety as fleet rates, not only as vessel totals.** Both stepped up in 2025 and again in 2026. A trigger at the 2024 rate (repairs under 3%, safety near zero) would have fired in 2025.
5. **Keep L96 as a budget-drift case**, mainly crew wages, and keep it off the unbudgeted list. A17 and F86 are the reference for budgeted-line control. F86 still needs the deferred-work review.
6. **Stop using the off-budget column and the risk label as controls** until someone defines what `Off_Budget_USD` is supposed to measure and until the risk label is rebuilt from exposure, overdue count, and the cost run rate together. Add the four missing vessels to the handover register or record why they are excluded.

A practical monthly pack for the next vessel is small: variance and non-budgeted dollars by category, a flag when either is worse than the prior three months, repairs and safety rates against the 2024 baseline, and a deferred-exposure line that is not allowed to hide inside the cost variance.
