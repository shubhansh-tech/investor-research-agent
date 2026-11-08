"""First-time setup guide for a ticker that has no folder yet (daily use only).

Teaching note
-------------
Instead of a bare "folder missing" message, the agent looks the company up on SEC EDGAR and
tells the owner exactly which filings to save, with direct links:
  * the latest 10-K (annual report) filed on or before today,
  * the latest 10-Q (quarterly report) for a period after that 10-K, if any,
  * the 10-Q for the same quarter one year earlier (needed for trailing twelve months),
  * optionally, up to 4 earlier 10-Ks for 5-year history (only if a standing decision uses it).
It also builds the two fetch logs (10-K/10-Q and 8-K) in the same layout as an EDGAR export,
so the owner does not have to export them by hand. Code picks the filings; no model is involved.
"""
from __future__ import annotations

import io
import json
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from . import config as C

SEC = "https://www.sec.gov"


@dataclass
class Doc:
    role: str             # what it is for, in plain words
    form: str
    filed: date
    period: date | None
    accession: str
    doc_url: str          # the filing itself (inline-XBRL .htm): the file to save
    index_url: str        # EDGAR's index page for the filing
    file_name: str        # the name to save it under


@dataclass
class SetupGuide:
    ticker: str
    company: str
    cik: int
    required: list[Doc] = field(default_factory=list)
    optional_history: list[Doc] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    log_10kq: bytes = b""
    log_8k: bytes = b""

    def summary(self) -> str:
        return (f"{self.ticker} is not set up yet. Save the {len(self.required)} filing(s) listed under "
                f"'First-time setup required for {self.ticker}' and the two fetch logs, then run again.")


def _get(url: str, log: list | None):
    if log is not None:
        log.append(url)
    req = urllib.request.Request(url, headers={"User-Agent": C.SEC_USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _d(s: str) -> date | None:
    try:
        return date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def build_guide(ticker: str, as_of: date, log: list | None = None, fetch=None) -> SetupGuide:
    """fetch(url) -> parsed JSON; defaults to SEC's free JSON service (tests pass a stand-in)."""
    fetch = fetch or (lambda u: _get(u, log))
    tickers = fetch(f"{SEC}/files/company_tickers.json")
    hit = next((v for v in tickers.values() if str(v.get("ticker", "")).upper() == ticker.upper()), None)
    if hit is None:
        raise ValueError(f"ticker {ticker} was not found on SEC EDGAR (check the spelling)")
    cik = int(hit["cik_str"])
    sub = fetch(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    recent = sub["filings"]["recent"]
    n = len(recent["form"])
    col = lambda k: recent.get(k) or [""] * n  # noqa: E731
    rows = []
    for i in range(n):
        acc = col("accessionNumber")[i]
        folder = f"{SEC}/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
        rows.append({"form": col("form")[i], "filed": _d(col("filingDate")[i]), "period": _d(col("reportDate")[i]),
                     "acc": acc, "doc": col("primaryDocument")[i], "desc": col("primaryDocDescription")[i],
                     "items": col("items")[i], "index": f"{folder}/{acc}-index.htm", "folder": folder})
    rows = [r for r in rows if r["filed"] and r["filed"] <= as_of]
    g = SetupGuide(ticker.upper(), sub.get("name") or hit.get("title", ""), cik)

    def doc(r, role) -> Doc:
        name = r["doc"] or f"{r['acc']}.htm"
        return Doc(role, r["form"], r["filed"], r["period"], r["acc"], f"{r['folder']}/{name}", r["index"], name)

    # Originals only (amendments such as 10-K/A rarely carry the full statements).
    tenk = sorted([r for r in rows if r["form"] == "10-K" and r["period"]], key=lambda r: r["period"])
    tenq = sorted([r for r in rows if r["form"] == "10-Q" and r["period"]], key=lambda r: r["period"])
    if not tenk:
        g.problems.append("no 10-K (annual report) found on EDGAR for this company; it may file 20-F or 40-F "
                          "(foreign issuers), which this agent does not read yet")
        return _with_logs(g, rows)
    k = tenk[-1]
    g.required.append(doc(k, f"Latest annual report (fiscal year ended {k['period']})"))
    later = [q for q in tenq if q["period"] > k["period"]]
    if later:
        cur = later[-1]
        g.required.append(doc(cur, f"Latest quarterly report (period ended {cur['period']})"))
        target = cur["period"].replace(year=cur["period"].year - 1)
        prior = next((q for q in tenq if abs((q["period"] - target).days) <= 7), None)
        if prior:
            g.required.append(doc(prior, f"Same quarter one year earlier (period ended {prior['period']}), "
                                         "needed for trailing twelve months"))
        else:
            g.problems.append(f"the 10-Q for the period ended about {target} is not in EDGAR's recent list; "
                              "find it on the company's EDGAR page")
    for r in reversed(tenk[-5:-1]):
        g.optional_history.append(doc(r, f"Earlier annual report (fiscal year ended {r['period']})"))
    return _with_logs(g, rows)


def _log_bytes(rows: list[dict], with_items: bool = False) -> bytes:
    df = pd.DataFrame([{"Form Type": r["form"], "Form Description": r["desc"] or r["form"],
                        "Filing Date": r["filed"], "Reporting Date": r["period"] or r["filed"],
                        **({"Items": r["items"]} if with_items else {}),
                        "Filings URL": r["index"], "Accession Number": r["acc"]} for r in rows])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _with_logs(g: SetupGuide, rows: list[dict]) -> SetupGuide:
    """The fetch logs record what was on EDGAR when the owner downloaded: the same layout as EDGAR's export.
    From the next run on, any filing not in these logs counts as new and is asked for by name."""
    g.log_10kq = _log_bytes([r for r in rows if r["form"] in C.REQUIRED_FORMS])
    # 8-K item numbers (e.g. 2.02 = results of operations / earnings, 4.02 = restatement) are kept in the log.
    g.log_8k = _log_bytes([r for r in rows if r["form"] in {"8-K", "8-K/A"}], with_items=True)
    return g
