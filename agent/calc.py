"""The calculator: TTM ROE and Owner Earnings Yield, with every input cited.

Teaching note
-------------
The AI never types a number. It only names WHICH line items to use (e.g.
"us-gaap:ShareBasedCompensation is a non-cash charge"). This module looks those
items up in the parsed filings and does the arithmetic. So a hallucinated number is
impossible by construction, and the validator can re-check every value.

TTM (trailing twelve months) for a flow item such as net income:
    TTM = latest 10-K full year + current year-to-date - prior-year year-to-date
If no 10-Q has been filed since the 10-K, TTM = the 10-K year.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .filings import FilingRow, TTMSet, match_log_row
from .ixbrl import Fact, Filing

NI_CONCEPTS = ["us-gaap:NetIncomeLoss", "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic", "us-gaap:ProfitLoss"]
EQUITY_CONCEPTS = ["us-gaap:StockholdersEquity", "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
DA_CONCEPTS = ["us-gaap:DepreciationDepletionAndAmortization", "us-gaap:DepreciationAndAmortization",
               "us-gaap:DepreciationAmortizationAndAccretionNet", "us-gaap:DepreciationAmortizationAndOther"]
DEP_CONCEPTS = ["us-gaap:Depreciation", "us-gaap:DepreciationNonproduction"]


@dataclass
class Citation:
    form: str
    period_end: str
    section: str
    label: str
    concept: str
    value: float
    file: str
    url: str

    def short(self) -> str:
        return f"{self.form} {self.period_end}, {self.section}: \"{self.label}\""


@dataclass
class Input:
    name: str
    value: float | None
    how: str = ""                      # arithmetic shown to the reviewer
    citations: list[Citation] = field(default_factory=list)
    note: str = ""


@dataclass
class Metric:
    name: str
    value: float | None                # a ratio, e.g. 0.1837
    flag: str = ""                     # "", "not meaningful", "withheld"
    formula: str = ""
    inputs: list[Input] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


@dataclass
class Mapping:
    """Which line items feed Owner Earnings. Proposed by the AI, applied by code."""
    da_concept: str | None = None
    dep_concept: str | None = None
    other_non_cash: list[str] = field(default_factory=list)
    working_capital: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)


def fmt_money(v: float | None) -> str:
    if v is None:
        return "n/a"
    m = v / 1e6
    s = f"${abs(m):,.0f}M" if abs(m) >= 100 else f"${abs(m):,.1f}M"
    return f"-{s}" if v < 0 else s


def pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


class Calculator:
    def __init__(self, ttm: TTMSet, logs: list[FilingRow]):
        self.ttm, self.logs = ttm, logs

    # ------------------------------------------------------------ helpers
    def cite(self, f: Filing, fact: Fact) -> Citation:
        row = match_log_row(f, self.logs)
        return Citation(f.form, f.period_end.isoformat(), fact.section, fact.label or fact.concept, fact.concept,
                        fact.displayed_value if fact.section.endswith("Cash Flows") else fact.value,
                        f.path.name, row.url if row else "")

    def _annual(self, f: Filing, concept: str) -> Fact | None:
        return f.duration(concept, f.period_end, min_days=330, max_days=380)

    def _ytd(self, f: Filing, concept: str) -> Fact | None:
        return f.duration(concept, f.period_end, start=f.ytd_start())

    def flow(self, name: str, concepts: list[str], displayed: bool = False) -> Input:
        """TTM value of a flow item, trying concepts in order."""
        t = self.ttm
        if t.annual is None:
            return Input(name, None, note=f"{name}: latest 10-K missing")
        val = lambda fact: fact.displayed_value if displayed else fact.value  # noqa: E731
        last_missing = ""
        for c in concepts:
            a = self._annual(t.annual, c)
            if a is None:
                last_missing = f"{name}: {c} not found in 10-K {t.annual.period_end}"
                continue
            if t.current_q is None:
                return Input(name, val(a), f"10-K FY {fmt_money(val(a))}", [self.cite(t.annual, a)])
            cur = self._ytd(t.current_q, c)
            pri = self._ytd(t.prior_q, c) if t.prior_q else None
            if cur is None or pri is None:
                miss = t.current_q if cur is None else t.prior_q
                last_missing = f"{name}: {c} not found in 10-Q {miss.period_end if miss else 'prior-year'}"
                continue
            v = val(a) + val(cur) - val(pri)
            how = f"{fmt_money(val(a))} (10-K FY) + {fmt_money(val(cur))} (YTD {t.current_q.period_end}) - {fmt_money(val(pri))} (YTD {t.prior_q.period_end})"
            return Input(name, v, how, [self.cite(t.annual, a), self.cite(t.current_q, cur), self.cite(t.prior_q, pri)])
        return Input(name, None, note=last_missing or f"{name}: not found")

    def equity(self) -> tuple[Input, Input]:
        t = self.ttm
        if t.current_q is not None:
            end_f, end_d = t.current_q, t.current_q.period_end
            start_f, start_d = t.prior_q, t.prior_q.period_end if t.prior_q else None
        else:
            end_f, end_d = t.annual, t.annual.period_end
            start_f, start_d = t.annual, t.annual.period_end.replace(year=t.annual.period_end.year - 1)
        out = []
        for label, f, d in (("Equity at start of TTM period", start_f, start_d), ("Equity at end of TTM period", end_f, end_d)):
            fact = None
            if f is not None and d is not None:
                for c in EQUITY_CONCEPTS:
                    fact = f.instant(c, d)
                    if fact:
                        break
            if fact is None:
                out.append(Input(label, None, note=f"{label}: shareholders' equity at {d} not found"))
            else:
                out.append(Input(label, fact.value, f"{fmt_money(fact.value)} at {d}", [self.cite(f, fact)]))
        return out[0], out[1]

    # ------------------------------------------------------------ metrics
    def roe(self) -> Metric:
        ni = self.flow("TTM net income", NI_CONCEPTS)
        e0, e1 = self.equity()
        m = Metric("ROE", None, formula="ROE = TTM net income / average shareholders' equity (start and end of TTM period)",
                   inputs=[ni, e0, e1])
        m.missing = [i.note for i in (ni, e0, e1) if i.value is None]
        if m.missing:
            m.flag = "withheld"
            return m
        avg = (e0.value + e1.value) / 2
        m.inputs.append(Input("Average equity", avg, f"({fmt_money(e0.value)} + {fmt_money(e1.value)}) / 2"))
        if avg <= 0:
            m.flag = "not meaningful"
            m.assumptions.append("Average equity is zero or negative, so ROE is not meaningful.")
            return m
        m.value = ni.value / avg
        m.formula += f"\n= {fmt_money(ni.value)} / {fmt_money(avg)} = {pct(m.value)}"
        return m

    def owner_earnings_yield(self, mapping: Mapping, price: float | None, overrides: dict | None = None) -> Metric:
        overrides = overrides or {}
        m = Metric("Owner Earnings Yield", None,
                   formula=("Owner Earnings = TTM net income + D&A + other non-cash charges - maintenance capex "
                            "(assumed = depreciation) +/- working-capital changes; Yield = Owner Earnings / market cap"))
        ni = self.flow("TTM net income", NI_CONCEPTS)
        da = self.flow("Depreciation & amortization", [mapping.da_concept] if mapping.da_concept else DA_CONCEPTS, displayed=True)
        parts = [ni, da]
        for c in mapping.other_non_cash:
            parts.append(self.flow(f"Non-cash: {c.split(':')[-1]}", [c], displayed=True))
        for c in mapping.working_capital:
            parts.append(self.flow(f"Working capital: {c.split(':')[-1]}", [c], displayed=True))
        if "maintenance_capex" in overrides:
            mc = Input("Maintenance capex (reviewer override)", float(overrides["maintenance_capex"]),
                       f"{fmt_money(float(overrides['maintenance_capex']))} per Shubhansh's direction",
                       note="reviewer override")
            m.assumptions.append("Maintenance capex was used per direction of Shubhansh (Reject feedback).")
        else:
            mc = self.flow("Maintenance capex (= depreciation)", [mapping.dep_concept] if mapping.dep_concept else DEP_CONCEPTS)
            m.assumptions.append("Maintenance capex assumed equal to depreciation (research_rules.md).")
        m.inputs = parts + [mc]
        m.missing = [i.note for i in m.inputs if i.value is None]

        newest = max(self.ttm.used(), key=lambda f: f.period_end)
        shares = newest.shares_outstanding
        if shares is None:
            m.missing.append(f"share count not found on the cover page of {newest.form} {newest.period_end}")
        if price is None or price <= 0:
            m.missing.append("current share price missing or invalid")
        if m.missing:
            m.flag = "withheld"
            return m
        oe = sum(i.value for i in parts) - mc.value
        mcap = price * shares
        m.inputs.append(Input("Owner earnings", oe, " + ".join(fmt_money(i.value) for i in parts) + f" - {fmt_money(mc.value)}"))
        m.inputs.append(Input("Share count", shares, f"{shares:,.0f} shares, cover page of {newest.form} {newest.period_end} (as of {newest.shares_as_of})",
                              [Citation(newest.form, newest.period_end.isoformat(), "Cover page", "Shares outstanding",
                                        "dei:EntityCommonStockSharesOutstanding", shares, newest.path.name,
                                        (match_log_row(newest, self.logs).url if match_log_row(newest, self.logs) else ""))]))
        m.inputs.append(Input("Market cap", mcap, f"${price:,.2f} x {shares / 1e6:,.1f}M shares"))
        m.value = oe / mcap
        m.formula += f"\n= {fmt_money(oe)} / {fmt_money(mcap)} = {pct(m.value)}"
        return m


def balance_check(f: Filing, on: date) -> tuple[bool, str]:
    """Accounting identity: assets = liabilities + equity (incl. noncontrolling and temporary equity)."""
    a = f.instant("us-gaap:Assets", on)
    total = f.instant("us-gaap:LiabilitiesAndStockholdersEquity", on)
    liab = f.instant("us-gaap:Liabilities", on)
    eq = None
    for c in reversed(EQUITY_CONCEPTS):
        eq = f.instant(c, on)
        if eq:
            break
    if a is None:
        return False, f"{f.form} {on}: total assets not found"
    if total is not None and abs(a.value - total.value) > max(1.0, abs(a.value) * 1e-6):
        return False, f"{f.form} {on}: assets {fmt_money(a.value)} != liabilities and equity {fmt_money(total.value)}"
    if liab is not None and eq is not None:
        extra = 0.0
        for c in ("us-gaap:MinorityInterest", "us-gaap:TemporaryEquityCarryingAmountAttributableToParent",
                  "us-gaap:RedeemableNoncontrollingInterestEquityCarryingAmount"):
            x = f.instant(c, on)
            if x and eq.concept == "us-gaap:StockholdersEquity" and c == "us-gaap:MinorityInterest":
                extra += x.value
            elif x and c != "us-gaap:MinorityInterest":
                extra += x.value
        if abs(a.value - (liab.value + eq.value + extra)) <= max(1.0, abs(a.value) * 1e-3):
            return True, f"{f.form} {on}: assets {fmt_money(a.value)} = liabilities {fmt_money(liab.value)} + equity {fmt_money(eq.value + extra)}"
        if total is not None:
            return True, f"{f.form} {on}: assets {fmt_money(a.value)} = total liabilities and equity {fmt_money(total.value)} (components not separately reconciled)"
        return False, f"{f.form} {on}: assets {fmt_money(a.value)} != liabilities {fmt_money(liab.value)} + equity {fmt_money(eq.value + extra)}"
    if total is not None:
        return True, f"{f.form} {on}: assets {fmt_money(a.value)} = total liabilities and equity {fmt_money(total.value)}"
    return False, f"{f.form} {on}: liabilities and equity totals not found"
