# Pre-market Research Agent

A bounded, tool-using research agent for a self-directed investor. Before the market
opens it checks SEC EDGAR for new filings, computes trailing-twelve-month **ROE** and
**Owner Earnings Yield** with a citation for every input, labels material news, and
writes a cited brief of under 200 words. The investor reviews one row per ticker and
approves, rejects, asks or cancels. **It produces research only: no trade, order,
brokerage or messaging tool exists in this codebase.**

Built for the Product Faculty Agentic AI PM capstone (C11). Author and first user:
Shubhansh Karnick.

## Design in one line
The AI reads and writes; plain code checks and counts. The model chooses *which*
filing line items matter and writes the brief; code reads every number from the
filings' inline-XBRL tags, does all arithmetic, and validates the result. See
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Repository map
| Path | What it is |
|---|---|
| `app.py` | Streamlit review screen (Research, Evals, How it works) |
| `agent/ixbrl.py` | Reads tagged numbers, statement section and row label from SEC filings |
| `agent/filings.py` | Fetch logs, EDGAR list (live or saved snapshot), new-filing rule, ticker check, TTM selection |
| `agent/calc.py` | Calculator: TTM ROE, Owner Earnings Yield, accounting identity |
| `agent/news.py` | Synthetic test news, EDGAR event filings, material-event and prompt-injection detectors |
| `agent/llm.py`, `agent/prompts.py` | The single model call (Anthropic) and a deterministic mock |
| `agent/validator.py` | Checks that gate Approve |
| `agent/pipeline.py` | Orchestrator: observe, decide, act, check, stop |
| `agent/storage.py` | `analysis.xlsx`, the only file the agent writes |
| `evals/` | 15 fixed cases, scenario builder, grader, results |
| `data/` | `research_rules.md` and one folder per ticker |
| `tools/make_exmp_fixture.py` | Builds the fictional EXMP test company |

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...            # or tick "Offline mock model"
streamlit run app.py
python evals/run_evals.py --runs 3      # scorecard -> evals/results/
```

## Data layout (per ticker)
```
data/research_rules.md
data/<TICKER>/filings/                       10-K, 10-Q (inline-XBRL .htm) and Item 2.02/4.02 8-Ks
data/<TICKER>/10-K-10-Q_fetch_log.xlsx       EDGAR exports of what has been downloaded
data/<TICKER>/8-K_fetch_log.xlsx
data/<TICKER>/edgar_snapshot_TEST_only/      saved EDGAR filing lists (test mode only)
data/<TICKER>/synthetic-news_TEST_only/      invented articles tagged SYNTHETIC_TEST_DATA----TAG (test mode only)
data/<TICKER>/thesis_note.md                 written by the investor; read-only for the agent
```
Test mode never calls live EDGAR or news; daily use never reads `_TEST_only` folders.

## Status
MVP. Live news search, PROVISIONAL handling of Item 2.02 earnings 8-Ks and a price
feed are post-MVP; see the PRD's limitations section.
