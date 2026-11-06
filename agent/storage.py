"""analysis.xlsx: the ONLY file the agent writes. One row per run, per ticker.

Memory lives here, not in the model: the next run reads the last APPROVED row as
its baseline. Rejected and UNREVIEWED rows are kept for evaluation but never used as
a baseline. Test-mode rows are labelled and only ever serve as a test baseline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config as C

COLUMNS = [
    "run_id", "date_time", "ticker", "sector", "status", "roe", "roe_flag", "ttm_net_income", "average_equity",
    "roe_supporting_information", "owner_earnings_yield", "owner_earnings", "price", "share_count", "market_cap",
    "owner_earnings_yield_supporting_information", "provisional", "test_mode", "what_changed", "news_labels",
    "missing_information", "agent_brief", "shubhansh_brief", "reviewer_decision", "reviewer_input", "ask_answer",
]


NUMERIC = {"roe", "ttm_net_income", "average_equity", "owner_earnings_yield", "owner_earnings", "price",
           "share_count", "market_cap"}


def path_for(tdir: Path) -> Path:
    return tdir / C.ANALYSIS_FILE


def read(tdir: Path) -> pd.DataFrame:
    p = path_for(tdir)
    if not p.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_excel(p, dtype={"run_id": str})
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None
        if c not in NUMERIC:
            df[c] = df[c].astype(object)
    return df[COLUMNS]


def write(tdir: Path, df: pd.DataFrame) -> None:
    tdir.mkdir(parents=True, exist_ok=True)
    df[COLUMNS].to_excel(path_for(tdir), index=False)


def append(tdir: Path, record: dict) -> None:
    df = read(tdir)
    df = pd.concat([df, pd.DataFrame([{c: record.get(c) for c in COLUMNS}])], ignore_index=True)
    write(tdir, df)


def set_decision(tdir: Path, run_id: str, decision: str, reviewer_input: str = "", ask_answer: str | None = None) -> None:
    df = read(tdir)
    mask = df["run_id"].astype(str) == str(run_id)
    if decision == "CANCELLED":
        write(tdir, df[~mask])          # cancelled runs are not stored
        return
    df.loc[mask, "reviewer_decision"] = decision
    df.loc[mask, "reviewer_input"] = reviewer_input
    if decision == "APPROVED":
        df.loc[mask, "shubhansh_brief"] = reviewer_input
    if ask_answer is not None:
        df.loc[mask, "ask_answer"] = ask_answer
    write(tdir, df)


def baseline(tdir: Path, test_mode: bool) -> dict | None:
    df = read(tdir)
    if df.empty:
        return None
    flag = "Y" if test_mode else "N"
    ok = df[(df["reviewer_decision"] == "APPROVED") & (df["test_mode"].astype(str) == flag)]
    if ok.empty:
        return None
    r = ok.iloc[-1].to_dict()
    return {k: (None if pd.isna(v) else v) for k, v in r.items()}


MAX_UPLOAD_BYTES = 2_000_000
REQUIRED = {"run_id", "ticker", "status", "reviewer_decision", "test_mode"}


def load_upload(ledger: Path, data: bytes) -> str:
    """Load a decision log the owner downloaded earlier. Its contents are data, never instructions.
    Rows are merged by run_id into this session's log for each ticker found. Returns a one-line result."""
    import io
    import re
    if len(data) > MAX_UPLOAD_BYTES:
        return "Not loaded: file is larger than 2 MB."
    try:
        df = pd.read_excel(io.BytesIO(data), dtype={"run_id": str})
    except Exception:  # noqa: BLE001
        return "Not loaded: not a readable Excel file."
    missing = REQUIRED - set(df.columns)
    if missing:
        return f"Not loaded: not an analysis.xlsx from this app (missing columns: {', '.join(sorted(missing))})."
    df = df.dropna(subset=["run_id", "ticker"])
    loaded, approved = [], 0
    for ticker, part in df.groupby(df["ticker"].astype(str).str.upper().str.strip()):
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
            continue
        tdir = ledger / ticker
        cur = read(tdir)
        part = part.assign(ticker=ticker)
        merged = pd.concat([cur, part.reindex(columns=COLUMNS)], ignore_index=True)
        merged = merged.drop_duplicates(subset=["run_id"], keep="first")
        write(tdir, merged)
        loaded.append(f"{ticker} ({len(part)} row(s))")
        approved += int((part["reviewer_decision"] == "APPROVED").sum())
    if not loaded:
        return "Not loaded: no valid ticker rows found."
    return f"loaded {', '.join(loaded)}; {approved} approved run(s) available as baselines."
