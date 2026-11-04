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

## Still to decide
- **Unread 8-Ks:** the agent sees only an 8-K's title, not its text. Proposed: a clear,
  separate flag ("8-K filed, contents not read; check sec.gov"), not a "one-time item".
- **QUBT warrant revaluation** (`FairValueAdjustmentOfWarrants`, about −$17.7M TTM against a
  net loss of about −$15.0M).
- **Chubb "Other" operating line** (`IncreaseDecreaseInOtherOperatingCapitalNet`, about +$1,330M
  TTM). The AI includes it in some runs and not others, which caused the 9.9% vs 10.9% swing in
  Owner Earnings Yield.
