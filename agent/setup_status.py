"""Setup status of each ticker folder, for the "Setup & filings" tab.

Teaching note
-------------
The tab is a checklist. Code looks at what is in a ticker's folder and decides, for each of the
four steps, whether it is done, needs action, or is locked behind an earlier step:
  1. folder        the ticker's folder exists
  2. fetch logs    both logs (10-K/10-Q and 8-K) are saved
  3. filings       the saved filings can build trailing twelve months (a 10-K, plus the latest
                   10-Q after it and the same quarter a year earlier, when there is such a 10-Q)
  4. assumptions   optional; done when assumptions.md exists and its decisions read cleanly
Only the first unfinished required step is "action required", so one red section shows at a time.
A Research run that found a new filing on EDGAR also marks the ticker "new filing needed".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import config as C
from . import decisions as decisions_mod
from .filings import load_filings, select_ttm

TEST_ONLY_TICKERS = {"EXMP"}      # fictional company used only by test scenarios
DONE, ACTION, LOCKED, OPTIONAL = "done", "action", "locked", "optional"
STEP_NAMES = {1: "Folder", 2: "Fetch logs", 3: "Filings", 4: "assumptions.md"}


@dataclass
class Step:
    n: int
    state: str          # done | action | locked | optional
    detail: str


@dataclass
class TickerStatus:
    ticker: str
    steps: list[Step] = field(default_factory=list)
    filings: list[str] = field(default_factory=list)
    new_filings: list = field(default_factory=list)     # FilingRow items from the latest Research run
    problems: list[str] = field(default_factory=list)

    @property
    def next_step(self) -> Step | None:
        return next((s for s in self.steps if s.state == ACTION), None)

    @property
    def headline(self) -> str:
        if self.new_filings:
            forms = ", ".join(f"{r.form} filed {r.filing_date}" for r in self.new_filings)
            return f"🔴 {self.ticker} · :red[Action required]: new filing needed ({forms})"
        s = self.next_step
        if s:
            return f"🔴 {self.ticker} · :red[Action required]: Step {s.n} of 4 ({STEP_NAMES[s.n]})"
        return f"✅ {self.ticker} · Set up (each Research run checks EDGAR for newer filings)"


def list_tickers(root: Path, extra: list[str] | None = None) -> list[str]:
    found = sorted(p.name for p in root.iterdir()
                   if p.is_dir() and p.name.isupper() and p.name not in TEST_ONLY_TICKERS) if root.is_dir() else []
    for t in extra or []:
        if t not in found and t not in TEST_ONLY_TICKERS:
            found.append(t)
    return found


def ticker_status(root: Path, ticker: str, as_of: date, new_filings: list | None = None) -> TickerStatus:
    st = TickerStatus(ticker, new_filings=list(new_filings or []))
    tdir = root / ticker
    if not tdir.is_dir():
        st.steps = [Step(1, ACTION, "No folder yet"), Step(2, LOCKED, "After step 1"),
                    Step(3, LOCKED, "After step 2"), Step(4, LOCKED, "Optional, after step 3")]
        return st
    st.steps.append(Step(1, DONE, f"{ticker}/ exists"))

    logs = [l for l in (C.FETCH_LOG_10KQ, C.FETCH_LOG_8K) if (tdir / l).exists()]
    if len(logs) == 2:
        st.steps.append(Step(2, DONE, "Both fetch logs saved"))
    else:
        missing = [l for l in (C.FETCH_LOG_10KQ, C.FETCH_LOG_8K) if l not in logs]
        st.steps.append(Step(2, ACTION, "Missing: " + ", ".join(missing)))

    filings, errors = load_filings(tdir)
    st.filings = [f"{f.form} · period ended {f.period_end} · {f.path.name}" for f in filings]
    st.problems += errors
    if st.steps[-1].state != DONE:
        st.steps.append(Step(3, LOCKED, "After step 2"))
    else:
        ttm = select_ttm(filings, as_of)
        if ttm.problems or ttm.annual is None:
            st.steps.append(Step(3, ACTION, f"{len(filings)} saved; " + "; ".join(ttm.problems or ["latest 10-K missing"])))
        else:
            st.steps.append(Step(3, DONE, f"{len(filings)} saved; trailing twelve months can be built ({ttm.mode})"))

    a = tdir / "assumptions.md"
    if st.steps[-1].state != DONE:
        st.steps.append(Step(4, LOCKED, "Optional, after step 3"))
    elif not a.exists():
        st.steps.append(Step(4, OPTIONAL, "Not added (optional): one-time items will be flagged for review"))
    else:
        d = decisions_mod.load(tdir)
        if d.problems:
            st.steps.append(Step(4, ACTION, "assumptions.md has problems: " + "; ".join(d.problems)))
        else:
            st.steps.append(Step(4, DONE, f"Saved; {len(d.items)} standing decision(s) read cleanly"))
    return st
