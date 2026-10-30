## What testing on real filings changed

Each item was found by running the agent on real SEC filings (CB, QUBT), not on the
fictional EXMP fixture, which passed everything. Source material for PRD Q25/Q26.

| # | Found on | What broke | Fix | Why it matters |
|---|---|---|---|---|
| 1 | QUBT 10-K FY2025 | Net income cited to the *balance sheet*: the heading "Statements of Operations **and Comprehensive Loss**" was not recognised, and a sentence mentioning "balance sheets" switched the section. | Headings must start the line; "and comprehensive income/loss" accepted. | Citations would have pointed a reviewer to the wrong statement. |
| 2 | QUBT 10-K FY2025 | Investing and financing lines (e.g. purchases of securities, $1.2B) were offered to the model as "working capital" candidates. | Candidates stop at "Net cash provided by operating activities". | Removes a way for the model to inflate owner earnings by ~$1B. |
| 3 | CB 10-K FY2025 | 10-K rejected as "not a 10-K/10-Q": the cover date was split by formatting ("December 31 , 2025"). | Date reader tolerates spaces around the comma. | Without it, CB had no TTM at all. |
| 4 | CB filings | Same printed line tagged differently across the three filings, so TTM could not be computed. | Fallback to the identical printed row label in the same statement, disclosed on screen. | Real companies change tags; exact-match code silently fails. |
| 5 | CB filings | Chubb discloses **no depreciation figure**, so "maintenance capex = depreciation" cannot be applied. | Agent withholds Owner Earnings Yield (NEEDS INFORMATION) and names what is missing; `CB/assumptions.md` lets Shubhansh supply a standing figure that is cited as his assumption. | The no-guessing rule held on a real gap. Decision pending with the owner. |
| 6 | QUBT 10-Q Q2 2025 | "Accrued interest receivable" is not presented at all in the prior-year cash-flow statement, so OEY was withheld. | Rule added to `research_rules.md`: a line not presented anywhere in a statement is $0 for that period, shown as an assumption; a line presented without the needed period is still missing. | Distinguishes "nil" from "unknown" instead of guessing. |
| 7 | CB, QUBT EDGAR exports | Export has two title rows above the header and a footer link row. | Header row detected; footer rows skipped. | Fetch logs are user-exported files; the tool must accept them as EDGAR produces them. |
