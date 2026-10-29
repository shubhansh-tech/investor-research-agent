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
