# Owner-earnings policy decisions

Decided by Shubhansh, recorded with the reasoning. **The agent does not read this file.** It is
the human record. The decisions take effect only once they are written into the ticker's
`assumptions.md` and the code that applies them is built (planned as batch 2, then measured
with a full 45-run evaluation).

## Why these decisions exist: the per-ticker review

Owner earnings asks what a business **really earns for its owners in a normal year**. Reported
net income contains company-specific items that need a judgment call: keep, remove or average.
In the first real evaluation the AI kept asking about the same Chubb items every run, so every
Chubb row was REVIEW FIRST. When everything is flagged, nothing stands out ("crying wolf").

**The workflow this creates:**

1. **First run on a new ticker:** the agent surfaces the recurring company-specific items it
   cannot treat by rule (REVIEW FIRST).
2. **One-time review:** Shubhansh decides each item once, with the 5-year history in front of
   him, and records the decision in `<TICKER>/assumptions.md`.
3. **Daily runs:** the agent applies those decisions silently and flags only (a) items not yet
   decided and (b) decided items whose current figure breaks from their normal range (the
   alarms below).
4. **Revisit:** when a new 10-K arrives, when an alarm trips, or when the business changes
   (an acquisition, for example).

Later, decisions that hold for a whole sector (for example all P&C insurers) could become
**sector defaults** that new tickers start from and can override.

## Chubb (CB): decided 2026-11-04

Figures come from the FY2025 and FY2023 10-Ks (5 fiscal years, 2021–2025) and the trailing
twelve months (TTM) to 2026-06-30. "Net income" means net income attributable to Chubb.

| # | Item | Decision | Alarm |
|---|---|---|---|
| 1 | **Realized investment gains/losses**: profit or loss when Chubb *sells* an investment | **Include**, using the **5-year average** (about −$67M/yr; yearly range +$1,030M to −$1,085M). Show this year's figure beside it. | **Deviation:** flag if this year differs from the 5-year average by more than 5% of net income |
| 2 | **Market-risk-benefit value changes**: quarterly re-estimate of guarantees Chubb Life Re reinsured on variable annuities (closed to new business since 2007) | **Remove** (non-cash). The real payouts (about $0.2B in the next 12 months) already appear in operating cash flow. | **Size:** flag if the change exceeds 15% of net income |
| 3 | **Equity-method income**: Chubb's share of the profits of private-equity and similar funds it partly owns | **Include**, using the **5-year average** (about $1,083M/yr; range $1M to $2,435M). Show this year's figure beside it. | **Deviation:** as in #1 |
| 4 | **Investment-fund flows**: securities bought and sold inside funds Chubb consolidates (from Huatai, 2023), partly with outside investors' money | **Exclude** (not income, not wholly Chubb's money). Show this year's amount in the brief. | None. Real gains and losses on these funds reach net income through #1, which is alarmed. |

Maintenance capex assumption: $637M (see `CB/assumptions.md`). Chubb does not disclose
depreciation, so the same estimate is added back and the two cancel.

### The reasoning, in brief
- **#1, changed after discussion.** The first draft removed realized gains. Shubhansh argued
  that investing the premiums is part of running an insurer, so removing the gains entirely
  understates the business permanently. The 5-year data agreed: Chubb *lost* a net ~$334M over
  2021–2025, so removing them would have flattered it. Averaging handles management's timing
  choices; the deviation alarm catches a real shock.
- **#2.** Unlike #1, no cash moves when the estimate changes, so removing it does not miss real
  money. Counter-argument noted: three straight years of losses (2023–25) may be a real cost
  trend, which the size alarm and the brief keep visible.
- **#3, same logic as #1, and larger** (about 10% of net income, about 0.8 points of yield).
  Concern raised: the market reacts to this year, while an average lags. Answer: the metric uses
  the average (long-term value) and the screen shows the current figure; the deviation alarm
  would have flagged both 2021 (boom, 16% of net income) and 2022 (collapse, 21%).
- **#4.** Concern raised: can Chubb lose a lot here? Yes, but those losses appear in net income
  through #1, not in this cash-shuffling line. Outside investors hold about $5.1B of these
  entities, and their share is removed before Chubb's net income.

## Chubb (CB): further decisions, 2026-11-04/05

| # | Item | Decision | Alarm |
|---|---|---|---|
| 5 | **"Other" operating line** (`IncreaseDecreaseInOtherOperatingCapitalNet`): an unexplained catch-all of real cash. 2021–2025: +$3,325M, +$789M, +$1,819M, +$1,374M, +$16M; TTM +$1,330M | **Include as reported** (TTM, like the rest of owner earnings), always, so the yield is repeatable. Show the 5-year history beside it. | **Deviation:** flag when this year breaks sharply from its 5-year history |
| 6 | **Insurance float growth**: changes in unpaid losses, unearned premiums, future policy benefits, reinsurance balances and acquisition costs (2023 +$2,870M, 2024 +$5,371M, 2025 +$4,219M) | **Exclude from owner earnings.** Float is owed to future claimants, and what it earns for owners (investment income, underwriting result) is already in net income. | Not applicable |

**Float panel (new, beside the metrics):** float size, its **2-year** growth, and the P&C
combined ratio ((claims + costs) ÷ premiums; under 100% means an underwriting profit). Chubb does
not tag the combined ratio, so the AI reads it from the management discussion and quotes the
sentence, and code checks that the quote and number appear in the filing.

Reasoning:
- **#5.** Shubhansh's logic: it is real cash and its swings are Chubb's reality, so do not
  flatten it. Averaging an unknown would itself be a guess, and #1 and #3 are averaged only
  because they are known, market-driven items. Remaining caution: some swing is calendar
  arithmetic (the TTM jumped mainly because a −$1,711M half-year left the window); the history
  and the alarm make that visible.
- **#6.** Agreed after a worked example: 100 customers × $10 = $1,000 collected, about $900 owed
  in future claims. Owners earn the underwriting result plus investment income, not the $1,000.
  Adding 2-year float growth would add about 3.5 points of yield from money Chubb owes. Shubhansh's
  insight that float shows how management runs the risk is kept in the float panel, on a 2-year
  window (recent management behaviour).

## Averaging windows
- #1 realized gains and #3 equity-method income: **5 years** (a full market cycle, including
  the 2021 boom and the 2022 crash).
- Float panel growth: **2 years**.
- #5 "Other": not averaged (as reported).

## 8-K filings, decided 2026-11-04
- **Required files (the MVP checks they are actually present, not only listed in the fetch
  log):** the latest 10-K; the latest 10-Q after it plus the same quarter a year earlier; and
  every Item 2.02 (earnings) or 4.02 (restatement) 8-K filed in the last 12 months. For each
  such 8-K, download the main 8-K document and Exhibit 99.1 (the press release). A missing
  required file means NEEDS INFORMATION, naming the filing and its sec.gov link. About 4–5 8-Ks
  per company per year.
- **8-Ks are flagged by item number, as their own category** (never as a "one-time item"). The
  line names the item and says the contents have not been read, with the sec.gov link.
  - High (4.01 auditor change, 4.02 restatement): REVIEW FIRST.
  - Medium (5.02 executive or director change, 1.01 major agreement, 2.01 completed acquisition
    or sale): REVIEW FIRST.
  - Low (7.01, 8.01, 5.07, 9.01): one informational line, no flag.
- **Item numbers:** the EDGAR exports used for test data say only "Current report". Planned: a
  "Save EDGAR snapshot" action in daily use (live EDGAR includes item numbers) to refresh the
  test data.
- **Later:** read 8-K text automatically (Exhibit 99.1).

## QUBT, decided 2026-11-04
| Item | Decision | Alarm |
|---|---|---|
| **Warrant revaluation** (QPhoton warrants for up to 7.03M shares, revalued each quarter at the share price: 2024 −$40.5M, 2025 +$11.8M, TTM +$17.7M) | **Remove** (non-cash; it moves opposite to the business, since a falling stock price shows as a gain). Without it the TTM loss is about −$33M rather than −$15.0M. Show the amount in the brief. | None |

Noted for later: counting the 7.03M potential shares in a "fully diluted" share count (about 3%)
would depart from the PRD's cover-page share-count rule.

## Alarm base (all tickers)
Size and deviation alarms are measured against **the larger of |net income| and 1% of
shareholders' equity**, so they do not fire constantly for companies with tiny or negative
profit (for QUBT, the warrant item is 118% of net income but about 1.1% of equity).
