"""Build a throw-away data folder for one test scenario (PRD Q23: "test folders built
by copying or leaving out files"). Used by both the eval harness and the app's
Test-mode scenario picker. The real data folder is never modified.
"""
from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import config as C  # noqa: E402
from agent.filings import load_filings, read_filing_list, select_ttm  # noqa: E402

LIB = Path(__file__).parent / "news_library"
COMPANY = {"CB": "Chubb Limited", "QUBT": "Quantum Computing Inc.", "EXMP": "Example Holdings Inc."}


def resolve_ticker(ticker: str, src_root: Path) -> tuple[str, bool]:
    """Until real CB/QUBT filings are added, cases run on the fictional EXMP (marked as proxy)."""
    if (src_root / ticker / "filings").is_dir() and any((src_root / ticker / "filings").glob("*.htm*")):
        return ticker, False
    return "EXMP", True


def _write_list(path: Path, rows) -> None:
    pd.DataFrame([{
        "Form Type": r.form, "Form Description": r.description, "Filing Date": r.filing_date,
        "Reporting Date": r.report_date, "Filings URL": r.url, "Accession Number": r.accession} for r in rows]
    ).to_excel(path, index=False)


def build(case: dict, src_root: Path, dst_root: Path, as_of: date) -> tuple[Path, str, bool]:
    ticker, proxy = resolve_ticker(case["ticker"], src_root)
    if dst_root.exists():
        shutil.rmtree(dst_root)
    dst_root.mkdir(parents=True)
    ops = case.get("ops", [])
    if "empty_root" in ops:
        return dst_root, ticker, proxy
    shutil.copy(src_root / C.RULES_FILE, dst_root / C.RULES_FILE)
    t = dst_root / ticker
    shutil.copytree(src_root / ticker, t, ignore=shutil.ignore_patterns(C.ANALYSIS_FILE, C.THESIS_FILE))
    filings, _ = load_filings(t)

    for op in ops:
        if isinstance(op, dict) and "news" in op:
            nd = t / C.NEWS_DIR
            if nd.exists():
                shutil.rmtree(nd)
            nd.mkdir()
            for name in op["news"]:
                txt = (LIB / f"{name}.md").read_text().format(ticker=ticker, company=COMPANY.get(ticker, ticker))
                (nd / f"{name}.md").write_text(txt)
        elif op == "after_10k":
            k = max((f for f in filings if f.form.startswith("10-K")), key=lambda f: f.period_end)
            for f in filings:
                if f.form.startswith("10-Q") and f.period_end > k.period_end:
                    f.path.unlink()
            for logname, snapname in ((C.FETCH_LOG_10KQ, C.SNAPSHOT_10KQ),):
                for p in (t / logname, t / C.SNAPSHOT_DIR / snapname):
                    if p.exists():
                        rows = [r for r in read_filing_list(p) if not (r.form.startswith("10-Q") and r.report_date and r.report_date > k.period_end)]
                        _write_list(p, rows)
        elif op == "remove_prior_q":
            ttm = select_ttm(filings, as_of)
            if ttm.prior_q:
                ttm.prior_q.path.unlink()
        elif op == "add_wrong_ticker":
            q = src_root / "QUBT" / "filings"
            src = next(iter(sorted(q.glob("*.htm*"))), None) if q.is_dir() else None
            if src is not None and ticker != "QUBT":
                shutil.copy(src, t / "filings" / ("WRONG_" + src.name))
            else:
                sys.path.insert(0, str(ROOT / "tools"))
                from make_exmp_fixture import build as fx  # noqa: PLC0415
                (t / "filings" / "WRONG_qubt-20260630.htm").write_text(
                    fx("10-Q", "2026-06-30", ["H126", "H125"], ["2026-06-30", "2025-12-31"], 200_000_000,
                       "2026-08-01", "2026", "Q2", symbol="QUBT", name="Quantum Computing Inc."))
        elif op == "drop_latest_q_from_log":
            p = t / C.FETCH_LOG_10KQ
            rows = read_filing_list(p)
            qs = [r for r in rows if r.form.startswith("10-Q") and r.filing_date]
            latest = max(qs, key=lambda r: r.filing_date)
            _write_list(p, [r for r in rows if r is not latest])
        elif op == "remove_snapshot":
            shutil.rmtree(t / C.SNAPSHOT_DIR, ignore_errors=True)
        elif op == "remove_news_dir":
            shutil.rmtree(t / C.NEWS_DIR, ignore_errors=True)
    return dst_root, ticker, proxy
