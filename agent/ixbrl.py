"""Read the machine-readable numbers out of an SEC inline-XBRL (iXBRL) filing.

Teaching note
-------------
Every 10-K and 10-Q filed with the SEC since ~2019 is an HTML page in which each
number in the financial statements is wrapped in a hidden tag, for example

    <ix:nonFraction name="us-gaap:NetIncomeLoss" contextRef="c-12"
                    unitRef="usd" scale="6" decimals="-6">1,240</ix:nonFraction>

`name` says WHAT the number is, `contextRef` points to WHEN (a period or a date),
`scale="6"` means "in millions". Because the tag sits on the exact number printed in
the statement, code can read it without guessing. This module does only that:
plain, repeatable parsing. No AI here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import warnings

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Statement headings we track so every fact can be cited to a section.
_PRE = r"^\s*(unaudited\s+)?(condensed\s+)?(consolidated\s+)?(condensed\s+)?"
SECTION_PATTERNS = [
    ("Consolidated Balance Sheets", re.compile(_PRE + r"(balance\s+sheets?|statements?\s+of\s+financial\s+(position|condition))", re.I)),
    ("Consolidated Statements of Operations", re.compile(_PRE + r"statements?\s+of\s+(operations|income|earnings)(\s+and\s+comprehensive\s+(income|loss))?", re.I)),
    ("Consolidated Statements of Comprehensive Income", re.compile(_PRE + r"statements?\s+of\s+comprehensive\s+(income|loss)", re.I)),
    ("Consolidated Statements of Shareholders' Equity", re.compile(_PRE + r"statements?\s+of\s+(changes\s+in\s+)?(shareholders|stockholders)['’]?\s+(equity|deficit)", re.I)),
    ("Consolidated Statements of Cash Flows", re.compile(_PRE + r"statements?\s+of\s+cash\s+flows?", re.I)),
    ("Notes to Financial Statements", re.compile(r"^\s*notes\s+to\s+(the\s+)?(unaudited\s+)?(condensed\s+)?(consolidated\s+)?(condensed\s+)?financial\s+statements", re.I)),
]

STATEMENT_SECTIONS = {s for s, _ in SECTION_PATTERNS[:5]}


@dataclass
class Context:
    id: str
    start: date | None
    end: date | None          # for instants, end == the instant
    instant: bool
    has_dimensions: bool      # True = a segment/breakdown, not the company total


@dataclass
class Fact:
    concept: str              # e.g. "us-gaap:NetIncomeLoss"
    value: float              # signed value in base units (dollars, shares)
    shown_negative: bool      # printed in parentheses in the statement (effect on cash flow)
    context: Context
    unit: str
    section: str              # statement the number was printed in
    label: str                # row label printed next to the number
    raw_text: str             # the printed digits, e.g. "1,240"

    @property
    def displayed_value(self) -> float:
        """Value as the reader sees it in the statement (parentheses = negative)."""
        mag = abs(self.value)
        return -mag if self.shown_negative else mag


@dataclass
class Filing:
    path: Path
    form: str                       # 10-K / 10-Q
    period_end: date | None
    fiscal_year_focus: str | None
    fiscal_period_focus: str | None
    trading_symbols: list[str]
    registrant: str | None
    cik: str | None
    shares_outstanding: float | None
    shares_as_of: date | None
    facts: list[Fact] = field(default_factory=list)

    # ---- lookups -------------------------------------------------------
    def total_facts(self, concept: str) -> list[Fact]:
        return [f for f in self.facts if f.concept == concept and not f.context.has_dimensions]

    def instant(self, concept: str, on: date) -> Fact | None:
        cands = [f for f in self.total_facts(concept) if f.context.instant and f.context.end == on]
        return _prefer_statement(cands)

    def duration(self, concept: str, end: date, min_days: int = 0, max_days: int = 400, start: date | None = None) -> Fact | None:
        cands = []
        for f in self.total_facts(concept):
            c = f.context
            if c.instant or c.end != end or c.start is None:
                continue
            days = (c.end - c.start).days
            if start is not None and c.start != start:
                continue
            if min_days <= days <= max_days:
                cands.append(f)
        # longest duration ending on `end` = year-to-date
        if not cands:
            return None
        longest = max((f.context.end - f.context.start).days for f in cands)
        return _prefer_statement([f for f in cands if (f.context.end - f.context.start).days == longest])

    def ytd_start(self) -> date | None:
        """Start date of the year-to-date period this filing reports."""
        starts = [
            f.context.start for f in self.facts
            if not f.context.instant and f.context.end == self.period_end and f.context.start and not f.context.has_dimensions
        ]
        return min(starts) if starts else None

    def cash_flow_facts(self, end: date, start: date) -> list[Fact]:
        out, seen = [], set()
        for f in self.facts:
            c = f.context
            if f.section != "Consolidated Statements of Cash Flows" or c.has_dimensions or c.instant:
                continue
            if c.end == end and c.start == start and f.concept not in seen:
                if f.concept == "us-gaap:NetCashProvidedByUsedInOperatingActivities" or \
                        f.concept.startswith("us-gaap:NetCashProvidedByUsedInOperatingActivities"):
                    break  # operating section ends here; investing/financing lines are not candidates
                out.append(f)
                seen.add(f.concept)
        return out


def _prefer_statement(cands: list[Fact]) -> Fact | None:
    if not cands:
        return None
    for f in cands:
        if f.section in STATEMENT_SECTIONS:
            return f
    return cands[0]


def _d(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def _parse_text_date(s: str) -> date | None:
    d = _d(s)
    if d:
        return d
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s or "")
    if m and m[1].lower() in _MONTHS:
        return date(int(m[3]), _MONTHS[m[1].lower()], int(m[2]))
    return None


def _number(tag: Tag) -> float:
    txt = tag.get_text(strip=True)
    fmt = (tag.get("format") or "").lower()
    if "fixed-zero" in fmt or "zerodash" in fmt or txt in {"", "-", "—", "–"}:
        val = 0.0
    else:
        digits = re.sub(r"[^\d.]", "", txt.replace(",", "") if "comma-decimal" not in fmt else txt.replace(".", "").replace(",", "."))
        val = float(digits) if digits else 0.0
    scale = int(tag.get("scale") or 0)
    val *= 10 ** scale
    if tag.get("sign") == "-":
        val = -val
    return val


def _row_label(tag: Tag) -> str:
    tr = tag.find_parent("tr")
    if tr is None:
        return ""
    for td in tr.find_all(["td", "th"]):
        t = td.get_text(" ", strip=True)
        if t and not re.fullmatch(r"[\s$()\-—–,.\d%]*", t):
            return re.sub(r"\s+", " ", t)[:140]
    return ""


def _shown_in_parentheses(tag: Tag) -> bool:
    td = tag.find_parent(["td", "th"])
    if td is None:
        prev = tag.previous_sibling
        return isinstance(prev, NavigableString) and prev.strip().endswith("(")
    before = ""
    for el in td.descendants:
        if el is tag:
            break
        if isinstance(el, NavigableString):
            before += str(el)
    if "(" in before:
        return True
    prev_td = td.find_previous_sibling(["td", "th"])
    if prev_td is not None and prev_td.get_text(strip=True).endswith("("):
        return True
    return False


def parse_filing(path: str | Path) -> Filing:
    path = Path(path)
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")

    contexts: dict[str, Context] = {}
    for c in soup.find_all("xbrli:context"):
        start = c.find("xbrli:startdate")
        end = c.find("xbrli:enddate")
        inst = c.find("xbrli:instant")
        has_dims = c.find("xbrli:segment") is not None or c.find("xbrldi:explicitmember") is not None
        if inst is not None:
            d = _d(inst.get_text())
            contexts[c.get("id")] = Context(c.get("id"), d, d, True, has_dims)
        else:
            contexts[c.get("id")] = Context(c.get("id"), _d(start.get_text() if start else None),
                                            _d(end.get_text() if end else None), False, has_dims)

    dei: dict[str, list[tuple[str, str]]] = {}
    for t in soup.find_all("ix:nonnumeric"):
        name = t.get("name", "")
        if name.startswith("dei:"):
            dei.setdefault(name, []).append((t.get_text(" ", strip=True), t.get("contextref", "")))

    facts: list[Fact] = []
    section = "Cover page / other"
    shares, shares_date = None, None
    for el in soup.descendants:
        if isinstance(el, NavigableString):
            s = str(el).strip()
            if 8 <= len(s) <= 110:
                for name, pat in SECTION_PATTERNS:
                    if pat.match(s):
                        section = name
                        break
            continue
        if not isinstance(el, Tag) or el.name != "ix:nonfraction":
            continue
        ctx = contexts.get(el.get("contextref", ""))
        if ctx is None:
            continue
        concept = el.get("name", "")
        f = Fact(concept, _number(el), _shown_in_parentheses(el), ctx, el.get("unitref", ""),
                 section, _row_label(el), el.get_text(strip=True))
        facts.append(f)
        if concept == "dei:EntityCommonStockSharesOutstanding" and not ctx.has_dimensions:
            shares = (shares or 0) + f.value if shares and shares_date == ctx.end else f.value
            shares_date = ctx.end

    def first(name: str) -> str | None:
        v = dei.get(name)
        return re.sub(r"\s+", " ", v[0][0]).strip() if v else None

    symbols = sorted({v.upper() for v, _ in dei.get("dei:TradingSymbol", []) if v})
    return Filing(
        path=path,
        form=(first("dei:DocumentType") or "").upper(),
        period_end=_parse_text_date(first("dei:DocumentPeriodEndDate") or ""),
        fiscal_year_focus=first("dei:DocumentFiscalYearFocus"),
        fiscal_period_focus=first("dei:DocumentFiscalPeriodFocus"),
        trading_symbols=symbols,
        registrant=first("dei:EntityRegistrantName"),
        cik=(first("dei:EntityCentralIndexKey") or "").lstrip("0") or None,
        shares_outstanding=shares,
        shares_as_of=shares_date,
        facts=facts,
    )
