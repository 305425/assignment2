// Builds outputs/Management_Summary.docx from outputs/summary_figures.json.
// Run from the Assignment2 folder after `py -3 -m analysis.run_all`:
//   node docgen/build_summary.js
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, LevelFormat, Packer, PageNumber,
  Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType,
} = require("docx");

const root = path.resolve(__dirname, "..");
const F = JSON.parse(fs.readFileSync(path.join(root, "outputs", "summary_figures.json"), "utf8"));

const FONT = "Arial";
const NAVY = "1F3A5F";
const GREY = "595959";
const PAGE_W = 11906;
const MARGIN = 1000;
const CONTENT_W = PAGE_W - 2 * MARGIN;

const unsigned = (s) => s.replace(/^-/, "");

const run = (text, opts = {}) => new TextRun({ text, font: FONT, size: 18, ...opts });
const bold = (text, opts = {}) => run(text, { bold: true, ...opts });

const para = (children, opts = {}) =>
  new Paragraph({ spacing: { after: 70, line: 252 }, ...opts, children: [].concat(children) });

const heading = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 150, after: 60 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: NAVY, space: 1 } },
    children: [new TextRun({ text, font: FONT, size: 21, bold: true, color: NAVY })],
  });

const bullet = (children, ref = "bullets") =>
  new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 40, line: 252 },
    children: [].concat(children),
  });

const border = { style: BorderStyle.SINGLE, size: 2, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, width, { header = false, boldText = false, align = AlignmentType.LEFT } = {}) {
  const children = [].concat(text).map((t) =>
    typeof t === "string"
      ? new TextRun({ text: t, font: FONT, size: 17, bold: header || boldText,
                      color: header ? "FFFFFF" : undefined })
      : t);
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    shading: header ? { type: ShadingType.CLEAR, color: "auto", fill: NAVY } : undefined,
    children: [new Paragraph({ alignment: align, children })],
  });
}

function table(widths, header, rows, { rightAlign = [], boldFirstCol = false } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const align = (j) => (rightAlign.includes(j) ? AlignmentType.RIGHT : AlignmentType.LEFT);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true,
                     children: header.map((h, j) => cell(h, widths[j], { header: true, align: align(j) })) }),
      ...rows.map((r) => new TableRow({
        children: r.map((v, j) => cell(v, widths[j], {
          align: align(j), boldText: j === 0 && (r.bold || boldFirstCol) })),
      })),
    ],
  });
}

// Plain-language wording for the decision groups produced by analysis/findings.py.
const PLAIN_DECISION = {
  "Fix cost control and deferred work before accepting responsibility":
    "Do not take over until spending and postponed work are both fixed",
  "Investigate unbudgeted spend; create a handover record":
    "Find out why it spends money with no budget; create a handover record",
  "Monitor budget drift; create a handover record":
    "Watch spending as it is starting to go over budget; create a handover record",
  "Deferred-work decision; cost control can continue":
    "Spending is fine; decide who pays for the large amount of postponed work",
  "Continue; create a handover record": "Spending is fine; create a handover record",
  "Continue current control": "Spending is fine; keep as is",
};

// ------------------------------------------------------------------ content

const title = [
  new Paragraph({
    spacing: { after: 30 },
    children: [new TextRun({ text: "Vessel cost control: management summary", font: FONT,
                             size: 32, bold: true, color: NAVY })],
  }),
  para(run(`Covers GNMTC's 14 vessels from January 2024 to July 2026 (2026 has seven months of data). `
           + `The data is synthetic. Codes such as E05 point to the Evidence_Register sheet in `
           + `GNMTC_Vessel_Cost_Analysis.xlsx. Key terms are explained on page 2.`,
           { color: GREY, size: 16 }), { spacing: { after: 100 } }),
];

const answer = [
  heading("The short answer"),
  para([
    run("By June 2024, five vessels ("),
    bold(F.focus_vessels),
    run(") were already spending money that had no budget. Two of them, H72 and E48, were also "),
    bold(`${F.h72_h1.slice(1)} and ${F.e48_h1.slice(1)} over budget`),
    run(". These five vessels account for "),
    bold(`${F.focus_share} of the fleet's ${F.variance} overrun`),
    run(". The headline totals hid this, because other items came in under budget and cancelled out "
        + "part of the overspend. A simple monthly check of two things, spending with no budget and "
        + "the overspend over the last three months, would have flagged all five vessels in June 2024, the first month the check can be run on six months of history "
        + "(E05, E17). Whether the spending with no budget was extra spend, or budgeted work booked outside the budget, cannot be told from this data (E21)."),
  ]),
];

const impact = [
  heading("The money"),
  table(
    [4300, 1900, 1866, 1800],
    ["Measure", "Jan 2024 to Jul 2026", "Average per month", "Evidence"],
    [
      ["Budget (planned spend)", F.budget, "", "E01"],
      ["Actual spend", F.actual, "", "E01"],
      Object.assign([`Overrun: actual minus budget (${F.variance_pct})`, F.variance,
                     `${F.pace["2024"]} (2024) to ${F.pace["2026"]} (2026)`, "E01, E04"], { bold: true }),
      ["   made up of: spending with no budget (overspend)", `+${F.nonbudgeted}`, "", "E02, E03"],
      ["   made up of: budgeted items vs their budget (underspend)", F.budgeted_gap, "", "E02"],
      ["Postponed work still to be paid for (figures not checked)", F.deferred, "", "E14"],
    ],
    { rightAlign: [1, 2] },
  ),
  para(run(`The overrun got bigger each year: ${F.pct_by_year["2024"]} in 2024, ${F.pct_by_year["2025"]} `
           + `in 2025 and ${F.pct_by_year["2026"]} in 2026. Postponed work is a future cost, not money `
           + `already spent, and its figures have no stated method or date, so it is kept separate `
           + `from the overrun.`, { size: 16, color: GREY }),
       { spacing: { before: 50, after: 60 } }),
];

const findings = [
  heading("Five findings"),
  bullet([bold("Most of the problem is spending with no budget, on five vessels. "),
          run(`They spent ${F.nonbudgeted} with no budget, which is more than the whole overrun. Items `
              + `that did have a budget were ${unsigned(F.budgeted_gap)} under it in total (E02, E03).`)],
         "numbers"),
  bullet([bold("The problems lasted; they were not one-offs. "),
          run(`H72 and E48 were over budget in ${F.h72_months} and ${F.e48_months} of 31 months, and got `
              + `worse every year, reaching ${F.h72_2026.slice(1)} and ${F.e48_2026.slice(1)} over in 2026 (E05).`)],
         "numbers"),
  bullet([bold("Repairs and safety costs rose on all vessels. "),
          run(`Over budget by year (2024, 2025, 2026): repairs ${F.repairs.map((s) => s.slice(1)).join(", ")}; `
              + `safety ${F.safety.map((s) => s.slice(1)).join(", ")}. The data does not show why (E06, E20).`)],
         "numbers"),
  bullet([bold("Totals can hide problems. "),
          run(`Crew wages look on budget (only ${F.wages_var} over), but that is because ${F.wages_nb} of `
              + `wages with no budget was cancelled out by ${unsigned(F.wages_gap)} saved on budgeted wages. `
              + `K56 is only ${F.k56_var} over budget overall, yet spent ${F.k56_nb} with no budget (E07, E08).`)],
         "numbers"),
  bullet([bold("The handover data cannot be trusted yet. "),
          run(`The risk label in the handover sheet matches neither spending nor postponed work; `
              + `${F.missing_records} have no handover record; K56 shows more overdue issues than open `
              + `issues; and the Off_Budget_USD column does not match spending with no budget (E10 to E13).`)],
         "numbers"),
];

const handover = [
  heading("What to do with each vessel at handover"),
  para(run("Each vessel is judged on two separate questions: is its spending under control, and does it "
           + "carry a large amount of postponed work (over $120,000, or 4 or more overdue issues)? The risk "
           + "label in the source data is not used.", { size: 17 })),
  table(
    [5600, 4266],
    ["Decision", "Vessels"],
    F.handover_groups.map((g) => [PLAIN_DECISION[g.decision] || g.decision, g.vessels]),
  ),
  para(run("Four vessels are marked Handover Review in the source data. Only H72 has a spending problem. "
           + "D49, I27 and F86 spend within budget, but each carries $159,000 to $170,000 of postponed "
           + "work, so taking them over depends on checking those figures.", { size: 17 }),
       { spacing: { before: 60, after: 60 } }),
];

const ew = [
  heading("Spotting problems early"),
  para([
    run("Each month, a simple rule escalates a vessel if, over the last three months, it was more than "
        + "5% over budget or spent more than $10,000 with no budget. It was checked on "
        + `${F.ew_test_rows} vessel-months from 2026 that were not used to design it: `),
    bold(`${F.ew.precision} of its escalations were correct and it caught ${F.ew.recall} of the cases `
         + `where a vessel went on to overspend in the next three months`),
    run(`. Of the vessel-months that stayed fine, ${F.ew.false_alarms} were flagged by mistake. `
        + `That is a little ahead of just checking last month (${F.ew.base_precision} correct, `
        + `${F.ew.base_recall} caught) and of a statistical model (${F.ew.lr_precision}, `
        + `${F.ew.lr_recall}), but with so few cases the gap is within chance. It also misses about one in three problems, and almost all the successes are the five persistent vessels. In ${F.latest_period} it escalates ${F.latest_escalate}. `
        + `Its weak spot is a vessel that starts going over budget without any spending outside budget: `
        + `it flagged L96 and I27 about three months late (E16, E17).`),
  ]),
];

const recs = [
  heading("Recommendations"),
  bullet([bold("Start: "),
          run("report spending with no budget next to the overrun every month; require approval before "
              + "any purchase with no budget is made; run the early-warning rule at each month-end, and "
              + "send any vessel escalated two months in a row to management review (C01 to C03).")]),
  bullet([bold("Change: "),
          run("sign off each handover on spending and on postponed work separately, and keep a handover "
              + "record for every vessel; define what Off_Budget_USD and the risk label mean; check issue "
              + "counts; and require every postponed-work estimate to say how and when it was made (C05 to C08).")]),
  bullet([bold("Watch: "),
          run("every quarter, compare fleet repairs and safety spending with the year before. Every month, "
              + "watch the problem lines (H72 safety, E48 crew travel, K56 and B78 repairs) until they are "
              + "under budget three months in a row (C04, C10).")]),
  bullet([bold("Keep: "),
          run("the budget discipline on A17, F86 and G17, and use them as the model when setting budgets (C09).")]),
  bullet([bold("Before taking on another vessel: "),
          run("get a list of its postponed work, with how and when each estimate was made; agree who approves "
              + "spending with no budget; and review its first three months against budget. Link cost records "
              + "to maintenance, defect and purchase-order records so changes in cost can be explained (C11, C12).")]),
];

const terms = [
  heading("Key terms"),
  table(
    [2400, 7466],
    ["Term", "Meaning"],
    [
      ["Fleet", "All 14 vessels together."],
      ["Budget", "The planned spend for each vessel, cost category and month."],
      ["Overrun", "Actual spend minus budget. Above zero is an overspend; below zero is an underspend."],
      ["Spending with no budget", "Costs marked Non-Budgeted in the data: there was no budget for them at all."],
      ["Postponed work", "Maintenance or repairs put off until later (deferred). It still has to be paid for."],
      ["Escalate", "The early-warning rule's top level: management should review the vessel."],
      ["Vessel-month", "One vessel in one month, the unit the early-warning rule checks."],
    ],
    { boldFirstCol: true },
  ),
];

const limits = [
  heading("Limits"),
  para(run("The data is synthetic and only covers 31 months, so seasonal patterns and dry-dock cycles cannot "
           + "be separated from real trends. The findings on spending with no budget rely on a Budget_Status "
           + "label that has no written definition. Postponed-work figures have not been checked. The data "
           + "does not explain why repairs and safety costs rose. Full detail is in "
           + "Evidence_and_Limitations.md.", { size: 17 })),
];

const doc = new Document({
  creator: "Vessel cost control assessment",
  title: "Vessel cost control: management summary",
  styles: { default: { document: { run: { font: FONT, size: 18 } } } },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
                   style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
                   style: { paragraph: { indent: { left: 360, hanging: 280 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: PAGE_W, height: 16838 },
              margin: { top: 900, bottom: 900, left: MARGIN, right: MARGIN } },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "Page ", font: FONT, size: 14, color: GREY }),
                     new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: GREY })],
        })],
      }),
    },
    children: [...title, ...answer, ...impact, ...findings, ...handover, ...ew, ...recs, ...terms, ...limits],
  }],
});

const out = path.join(root, "outputs", "Management_Summary.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log(`Wrote ${out}`);
});
