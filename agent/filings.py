"""Deterministic filing checks: fetch logs, EDGAR's current list, new-filing rule,
ticker match and picking the three filings that trailing-twelve-month (TTM) needs.

Teaching note: these are yes/no questions with exact answers ("is this accession
number in the log?"), so they are plain code. Asking an AI would only add a chance
of being wrong.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from . import config as C
from .ixbrl import Filing, parse_filing

ACC_RE = re.compile(r"(\d{10}-\d{2}-\d{6})")
ACC_PATH_RE = re.compile(r"/(\d{18})/")
ITEM_RE = re.compile(r"\b(\d\.\d{2})\b")


@dataclass
class FilingRow:
    form: str
    description: str
    filing_date: date | None
    report_date: date | None
    url: str
    accession: str

    @property
    def items(self) -> set[str]:
        return set(ITEM_RE.findall(self.description or ""))

    @property
    def must_download(self) -> bool:
        base = self.form.upper().strip()
        if base in C.REQUIRED_FORMS:
            return True
        if base in {"8-K", "8-K/A"}:
            return bool(self.items & C.REQUIRED_8K_ITEMS)
        return False


def _to_date(v) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(str(v)).date()
    except Exception:
        return None


def accession_from(url: str, given: str | None) -> str:
    if given and ACC_RE.search(str(given)):
        return ACC_RE.search(str(given))[1]
    m = ACC_RE.search(url or "")
    if m:
        return m[1]
    m = ACC_PATH_RE.search(url or "")
    if m:
        s = m[1]
        return f"{s[:10]}-{s[10:12]}-{s[12:]}"
    return ""


def read_filing_list(path: Path) -> list[FilingRow]:
    """Read a fetch log or an EDGAR filing-list export (.xlsx or .csv)."""
    raw = pd.read_excel(path, header=None) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path, header=None)
    # EDGAR's export puts title rows ("EDGAR Entity Landing Page", "CIK: ...") above the header.
    hdr = next((i for i, r in raw.iterrows()
                if any(re.sub(r"[^a-z]", "", str(v).lower()) in {"formtype", "form"} for v in r.values)), 0)
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(v) for v in raw.iloc[hdr].values]
    cols = {re.sub(r"[^a-z]", "", str(c).lower()): c for c in df.columns}

    def col(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_form, c_desc = col("formtype", "form", "filingtype"), col("formdescription", "description")
    c_fd, c_rd = col("filingdate", "filed"), col("reportingdate", "reportingfor", "reportdate", "periodofreport")
    c_url, c_acc = col("filingsurl", "url", "filingurl", "link"), col("accessionnumber", "accessionno", "accession")
    out = []
    for _, r in df.iterrows():
        url = str(r[c_url]) if c_url and pd.notna(r[c_url]) else ""
        if not c_form or pd.isna(r[c_form]) or (c_fd and _to_date(r[c_fd]) is None):
            continue  # footer rows such as the landing-page link
        out.append(FilingRow(
            form=str(r[c_form]).strip() if c_form else "",
            description=str(r[c_desc]) if c_desc and pd.notna(r[c_desc]) else "",
            filing_date=_to_date(r[c_fd]) if c_fd else None,
            report_date=_to_date(r[c_rd]) if c_rd else None,
            url=url,
            accession=accession_from(url, r[c_acc] if c_acc else None),
        ))
    return out


# ---------------------------------------------------------------- EDGAR list
def edgar_list_live(ticker: str, log=None) -> list[FilingRow]:
    """EDGAR's current filing list from SEC's free JSON service (daily use only)."""
    headers = {"User-Agent": C.SEC_USER_AGENT, "Accept-Encoding": "identity"}

    def get(url):
        if log is not None:
            log.append(url)
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
            return json.loads(r.read().decode())

    tickers = get("https://www.sec.gov/files/company_tickers.json")
    cik = next((v["cik_str"] for v in tickers.values() if v["ticker"].upper() == ticker.upper()), None)
    if cik is None:
        raise ValueError(f"Ticker {ticker} not found on SEC EDGAR")
    sub = get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")["filings"]["recent"]
    rows = []
    for i, form in enumerate(sub["form"]):
        acc = sub["accessionNumber"][i]
        items = sub.get("items", [""] * len(sub["form"]))[i]
        rows.append(FilingRow(
            form=form,
            description=f"{sub.get('primaryDocDescription', [''] * 999)[i]} items {items}".strip(),
            filing_date=_to_date(sub["filingDate"][i]),
            report_date=_to_date(sub["reportDate"][i]),
            url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{acc}-index.htm",
            accession=acc,
        ))
    return rows


def edgar_list_snapshot(tdir: Path) -> list[FilingRow]:
    snap = tdir / C.SNAPSHOT_DIR
    rows = []
    for name in (C.SNAPSHOT_10KQ, C.SNAPSHOT_8K):
        if (snap / name).exists():
            rows += read_filing_list(snap / name)
    return rows


# ---------------------------------------------------------------- new-filing rule
@dataclass
class NewFilingResult:
    must_download: list[FilingRow] = field(default_factory=list)   # -> NEEDS INFORMATION
    news_filings: list[FilingRow] = field(default_factory=list)    # other 8-Ks, Form 4, NT forms (last 30 days)


def find_new_filings(edgar: list[FilingRow], log_10kq: list[FilingRow], log_8k: list[FilingRow], as_of: date) -> NewFilingResult:
    """A filing is new when its accession number is on EDGAR but not in the fetch logs.
    Only filings dated on/after the latest Filing Date in the relevant fetch log are
    checked (same-day filings are caught because the comparison is >=)."""
    have = {r.accession for r in log_10kq + log_8k if r.accession}
    latest_kq = max((r.filing_date for r in log_10kq if r.filing_date), default=date.min)
    latest_8k = max((r.filing_date for r in log_8k if r.filing_date), default=date.min)
    res = NewFilingResult()
    for r in edgar:
        if not r.filing_date or r.filing_date > as_of:
            continue
        form = r.form.upper()
        if r.must_download and r.accession not in have:
            floor = latest_8k if form.startswith("8-K") else latest_kq
            if r.filing_date >= floor:
                res.must_download.append(r)
        elif not r.must_download and r.filing_date >= as_of - timedelta(days=C.NEWS_LOOKBACK_DAYS):
            if form.startswith("8-K") or form in {"4", "4/A"} or form in C.LATE_FILING_FORMS:
                res.news_filings.append(r)
    return res


# ---------------------------------------------------------------- inventory + TTM
@dataclass
class TTMSet:
    annual: Filing | None
    current_q: Filing | None          # latest 10-Q after the 10-K (None => TTM = 10-K only)
    prior_q: Filing | None            # same quarter one year earlier
    problems: list[str] = field(default_factory=list)

    @property
    def mode(self) -> str:
        return "10-K only" if self.current_q is None else "10-K + current YTD - prior-year YTD"

    def used(self) -> list[Filing]:
        return [f for f in (self.annual, self.current_q, self.prior_q) if f is not None]


def load_filings(tdir: Path) -> tuple[list[Filing], list[str]]:
    files, errors = [], []
    for p in sorted((tdir / "filings").glob("*")):
        if p.suffix.lower() not in {".htm", ".html", ".xhtml"}:
            continue
        try:
            f = parse_filing(p)
            if not f.form or not f.period_end:
                errors.append(f"{p.name}: not an inline-XBRL 10-K/10-Q (no document type or period found)")
                continue
            files.append(f)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p.name}: could not be read ({e})")
    return files, errors


def ticker_mismatches(ticker: str, filings: list[Filing]) -> list[str]:
    bad = []
    for f in filings:
        if f.trading_symbols and ticker.upper() not in f.trading_symbols:
            bad.append(f"{f.path.name} belongs to {'/'.join(f.trading_symbols)} ({f.registrant}), not {ticker.upper()}")
        elif not f.trading_symbols:
            bad.append(f"{f.path.name} has no trading symbol on its cover page; cannot confirm it belongs to {ticker.upper()}")
    return bad


def select_ttm(filings: list[Filing], as_of: date) -> TTMSet:
    usable = [f for f in filings if f.period_end and f.period_end <= as_of]
    annuals = sorted([f for f in usable if f.form.startswith("10-K")], key=lambda f: f.period_end)
    if not annuals:
        return TTMSet(None, None, None, ["latest 10-K (annual report) is missing"])
    k = annuals[-1]
    qs = sorted([f for f in usable if f.form.startswith("10-Q") and f.period_end > k.period_end], key=lambda f: f.period_end)
    if not qs:
        return TTMSet(k, None, None)
    cur = qs[-1]
    target = cur.period_end.replace(year=cur.period_end.year - 1)
    prior = next((f for f in usable if f.form.startswith("10-Q") and abs((f.period_end - target).days) <= 7), None)
    probs = [] if prior else [f"prior-year 10-Q for the period ended {target.isoformat()} is missing (needed to compute TTM)"]
    return TTMSet(k, cur, prior, probs)


def match_log_row(f: Filing, log: list[FilingRow]) -> FilingRow | None:
    for r in log:
        if r.form.upper().startswith(f.form[:4]) and r.report_date and f.period_end and abs((r.report_date - f.period_end).days) <= 3:
            return r
    return None
