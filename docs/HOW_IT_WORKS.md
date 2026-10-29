## How it works

**One idea:** the AI reads and writes; plain code checks and counts.

| Step | Who does it | What happens |
|---|---|---|
| 1. Preflight | Code | Ticker folder, filings, fetch logs and `research_rules.md` exist. In test mode, the `_TEST_only` folders exist too. Anything missing → **NEEDS INFORMATION**, listing exactly what to add. |
| 2. Ticker check | Code | Each filing's cover page (its inline-XBRL `dei:TradingSymbol` tag) must match the ticker. A QUBT filing in the CB folder stops the run. |
| 3. New-filing check | Code | Compares EDGAR's filing list with your fetch logs by **accession number** (EDGAR's unique ID per filing). A 10-K, 10-Q or Item 2.02/4.02 8-K you have not saved → **NEEDS INFORMATION**; nothing is recalculated. |
| 4. TTM selection | Code | Picks the latest 10-K, the latest 10-Q after it and the same quarter a year earlier. TTM = 10-K + current YTD − prior-year YTD (or the 10-K alone right after a 10-K). |
| 5. Accounting check | Code | Assets = liabilities + equity on every balance sheet used. |
| 6. News and events | Code + AI | Code reads news (synthetic in test mode) and EDGAR event filings and runs keyword detectors for material events and embedded instructions. The AI labels each item positive / negative / mixed / uncertain with its causal path. |
| 7. Judgment | AI | Chooses **which cash-flow line items** are D&A, other non-cash charges and working-capital changes, flags one-time items, writes the brief (under 200 words) and checks the thesis. It never types a number. |
| 8. Calculator | Code | Looks up the chosen line items in the filings and computes ROE and Owner Earnings Yield, keeping a citation for every input. |
| 9. Validator | Code | Every number exists in the cited filing; no buy/sell language; approved sources only; no mixing of test and live data. Model-output problems get one retry, then the row stops at NEEDS INFORMATION. |
| 10. Human checkpoint | Shubhansh | Approve (records the review, no trade), Reject with guidance (reruns), Ask (brief unchanged) or Cancel. Every decision is logged in `analysis.xlsx`. |

**Status rules (most restrictive wins):** NEEDS INFORMATION (Approve disabled) › REVIEW FIRST (Approve unlocks after ticking "Flagged event reviewed") › READY.

**Memory:** none inside the model. Continuity comes from files: the last *approved* row in `analysis.xlsx` is the baseline; your `thesis_note.md` is read but never edited.

**Glossary**
- *Inline XBRL (iXBRL):* SEC filing format in which every number in the statements carries a hidden machine-readable tag.
- *Accession number:* EDGAR's unique ID for each filing, e.g. `0000896159-26-000045`.
- *TTM:* trailing twelve months.
- *ROE:* return on equity = TTM net income ÷ average shareholders' equity.
- *Owner Earnings Yield:* owner earnings ÷ market cap; owner earnings = net income + D&A + other non-cash charges − maintenance capex ± working-capital changes.
- *Deterministic:* gives the same answer every time; used for anything that must be exactly right.
