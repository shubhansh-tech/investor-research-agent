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

import re
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
    alarms: list[str] = field(default_factory=list)          # REVIEW FIRST reasons raised by decided-item alarms


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
    def __init__(self, ttm: TTMSet, logs: list[FilingRow], history: list[Filing] | None = None):
        self.ttm, self.logs = ttm, logs
        self.history = history or []          # older 10-Ks (<TICKER>/history/) for multi-year averages

    # ------------------------------------------------------------ multi-year history
    def annual_series(self, concepts: list[str], years: int) -> list[tuple[int, Fact, Filing]]:
        """Last `years` fiscal-year values of a cash-flow line, newest filing first for overlapping
        years (companies sometimes restate). Matches the tag, else the identical printed label."""
        t = self.ttm
        if t.annual is None:
            return []
        filings = [t.annual] + sorted([h for h in self.history if h.form.startswith("10-K")],
                                      key=lambda f: f.period_end, reverse=True)
        label = ""
        found: dict[int, tuple[Fact, Filing]] = {}
        for f in filings:
            for x in f.facts:
                c = x.context
                if not x.section.endswith("Cash Flows") or c.instant or c.has_dimensions or c.start is None:
                    continue
                if not 330 <= (c.end - c.start).days <= 380:
                    continue
                hit = x.concept in concepts or (label and self._norm(x.label) == self._norm(label))
                if hit:
                    label = label or x.label
                    found.setdefault(c.end.year, (x, f))
        last = t.annual.period_end.year
        return [(y, *found[y]) for y in range(last - years + 1, last + 1) if y in found]

    def _alarm_base(self, ni: Input) -> float:
        _, e1 = self.equity()
        return max(abs(ni.value or 0.0), 0.01 * abs(e1.value or 0.0))

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
            filings = [(t.annual, True)] + ([(t.current_q, False), (t.prior_q, False)] if t.current_q else [])
            if displayed:
                # Cash-flow adjustments: a line can appear on the income statement AND the cash-flow
                # statement with opposite signs (a realized gain is +income but a -adjustment).
                # Owner-earnings add-backs must use the cash-flow statement's version.
                facts = [self._cf_fact(f, c, annual) if f else None for f, annual in filings]
            else:
                facts = [self._annual(f, c) if annual else (self._ytd(f, c) if f else None) for f, annual in filings]
            # Companies sometimes tag the same printed line differently across filings.
            # Fall back to the identical row label in the same statement, and say so.
            label = next((x.label for x in facts if x is not None and x.label), "")
            section = next((x.section for x in facts if x is not None), "")
            sources = [f for f, _ in filings]          # which filing each fact is cited to
            # The current 10-Q prints last year's same period as a comparison column. When the
            # prior-year 10-Q lacks the line, that column is the company's own (and most recent)
            # figure for the period, so use it and cite the current 10-Q.
            comparative = ""
            if t.current_q is not None and t.prior_q is not None and facts[2] is None:
                comp = None
                if displayed:
                    comp = next((x for x in t.current_q.total_facts(c) if x.section.endswith("Cash Flows")
                                 and not x.context.instant and x.context.end == t.prior_q.period_end
                                 and x.context.start == t.prior_q.ytd_start()), None)
                comp = comp or t.current_q.duration(c, t.prior_q.period_end, start=t.prior_q.ytd_start())
                if comp is not None:
                    facts[2], sources[2] = comp, t.current_q
                    comparative = (f"prior-year YTD taken from the comparison column of 10-Q {t.current_q.period_end}, "
                                   f"because 10-Q {t.prior_q.period_end} does not show the line")
            matched_by_label = []
            for k, ((f, annual), x) in enumerate(zip(filings, facts)):
                if x is None and f is not None and label and section.endswith("Cash Flows"):
                    alt = self._by_label(f, label, annual)
                    if alt is not None:
                        facts[k] = alt
                        matched_by_label.append(f"{f.form} {f.period_end} tags it {alt.concept}")
            if displayed and any(x is None for x in facts):
                # last resort: the same concept elsewhere (e.g. income statement), disclosed
                for k, ((f, annual), x) in enumerate(zip(filings, facts)):
                    if x is None and f is not None and not (k == 2 and sources[2] is not f):
                        alt = self._annual(f, c) if annual else self._ytd(f, c)
                        if alt is not None and not alt.section.endswith("Cash Flows"):
                            facts[k] = alt
                            matched_by_label.append(f"{f.form} {f.period_end} read from {alt.section}")
                if not section:
                    section = next((x.section for x in facts if x is not None), "")
            # A cash-flow line the company does not present at all in a filing's cash-flow
            # statement is nil for that period (accounting convention). Narrow on purpose:
            # if the line appears anywhere in that statement but not for the needed period,
            # it is still treated as missing.
            not_presented = []
            if section.endswith("Cash Flows"):
                for k, ((f, annual), x) in enumerate(zip(filings, facts)):
                    if x is None and f is not None and not self._presented(f, c, label):
                        facts[k] = 0.0
                        not_presented.append(f"{f.form} {f.period_end}")
            if any(x is None for x in facts) or (t.current_q and t.prior_q is None) or all(x == 0.0 for x in facts):
                miss = next(((f, a) for (f, a), x in zip(filings, facts) if x is None), (t.prior_q, False))
                where = f"{miss[0].form} {miss[0].period_end}" if miss[0] else "prior-year 10-Q"
                last_missing = f"{name}: {c} not found in {where}"
                continue
            notes = [comparative] if comparative else []
            if matched_by_label:
                notes.append("matched by line label: " + "; ".join(matched_by_label))
            if not_presented:
                notes.append("line not presented in the cash-flow statement of " + ", ".join(not_presented) + "; treated as $0")
            note = "; ".join(notes)
            v_of = lambda x: 0.0 if x == 0.0 and not isinstance(x, Fact) else val(x)  # noqa: E731
            cites = [self.cite(src, x) for src, x in zip(sources, facts) if isinstance(x, Fact)]
            a = facts[0]
            if t.current_q is None:
                return Input(name, v_of(a), f"10-K FY {fmt_money(v_of(a))}", cites, note=note)
            cur, pri = facts[1], facts[2]
            v = v_of(a) + v_of(cur) - v_of(pri)
            how = f"{fmt_money(v_of(a))} (10-K FY) + {fmt_money(v_of(cur))} (YTD {t.current_q.period_end}) - {fmt_money(v_of(pri))} (YTD {t.prior_q.period_end})"
            if note:
                how += f" [{note}]"
            return Input(name, v, how, cites, note=note)
        if len(concepts) > 1:
            tried = ", ".join(c.split(":")[-1] for c in concepts)
            return Input(name, None, note=f"{name}: not disclosed in the filings used (looked for {tried})")
        return Input(name, None, note=last_missing or f"{name}: not found")

    @staticmethod
    def _cf_fact(f: Filing, concept: str, annual: bool) -> Fact | None:
        start = f.ytd_start()
        for x in f.total_facts(concept):
            c = x.context
            if not x.section.endswith("Cash Flows") or c.instant or c.end != f.period_end or c.start is None:
                continue
            if (annual and 330 <= (c.end - c.start).days <= 380) or (not annual and c.start == start):
                return x
        return None

    def _presented(self, f: Filing, concept: str, label: str) -> bool:
        want = self._norm(label)
        return any(x.section.endswith("Cash Flows") and (x.concept == concept or (want and self._norm(x.label) == want))
                   for x in f.facts)

    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z]", "", (s or "").lower())

    def _by_label(self, f: Filing, label: str, annual: bool) -> Fact | None:
        want = self._norm(label)
        for x in f.facts:
            c = x.context
            if x.section.endswith("Cash Flows") and not c.instant and not c.has_dimensions and c.end == f.period_end \
                    and self._norm(x.label) == want:
                days = (c.end - c.start).days
                if (annual and 330 <= days <= 380) or (not annual and c.start == f.ytd_start()):
                    return x
        return None

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

    def owner_earnings_yield(self, mapping: Mapping, price: float | None, overrides: dict | None = None,
                             decisions=None) -> Metric:
        overrides = overrides or {}
        m = Metric("Owner Earnings Yield", None,
                   formula=("Owner Earnings = TTM net income + D&A + other non-cash charges - maintenance capex "
                            "(assumed = depreciation) +/- working-capital changes; Yield = Owner Earnings / market cap"))
        decided = decisions.by_concept() if decisions is not None else {}
        ni = self.flow("TTM net income", NI_CONCEPTS)
        da_concept = mapping.da_concept if mapping.da_concept not in decided else None
        da = self.flow("Depreciation & amortization", [da_concept] if da_concept else DA_CONCEPTS, displayed=True)
        parts = [ni, da]
        # The model's line-item choices apply only to lines Shubhansh has NOT decided.
        for c in mapping.other_non_cash:
            if c not in decided:
                parts.append(self.flow(f"Non-cash: {c.split(':')[-1]}", [c], displayed=True))
        for c in mapping.working_capital:
            if c not in decided:
                parts.append(self.flow(f"Working capital: {c.split(':')[-1]}", [c], displayed=True))
        if decisions is not None and decisions.items:
            parts += self._apply_decisions(decisions, ni, m)
        if "maintenance_capex" in overrides:
            src = overrides.get("maintenance_capex_source", "Reject feedback")
            mc = Input("Maintenance capex (Shubhansh's assumption)", float(overrides["maintenance_capex"]),
                       f"{fmt_money(float(overrides['maintenance_capex']))} per Shubhansh ({src})",
                       note="reviewer override")
            m.assumptions.append(f"Maintenance capex was used per direction of Shubhansh ({src}), "
                                 "because the rule 'maintenance capex = depreciation' needs a figure he supplied.")
            # Depreciation is already deducted inside reported net income. If the company does not disclose
            # DEPRECIATION (an amortization line found as "D&A" does not count), the same estimate must be added
            # back, or depreciation is counted twice: once in net income and again as maintenance capex.
            dep = self.flow("Depreciation", [mapping.dep_concept] if mapping.dep_concept else DEP_CONCEPTS)
            da_is_depreciation = da.value is not None and any(
                "epreciation" in (x.concept + " " + x.label) for x in da.citations)
            if dep.value is None and not da_is_depreciation:
                est = float(overrides["maintenance_capex"])
                addback = Input("Depreciation add-back (same estimate)", est,
                                f"{fmt_money(est)} per Shubhansh ({src}); depreciation not disclosed", note="reviewer override")
                if da.value is None:
                    parts[1] = addback
                else:
                    parts.insert(2, addback)       # keep the amortization line too; it is a separate add-back
                m.assumptions.append("Depreciation is not disclosed, so the same estimate is added back to net income; "
                                     "with maintenance capex = depreciation the two cancel and the estimate does not "
                                     "change Owner Earnings.")
        else:
            mc = self.flow("Maintenance capex (= depreciation)", [mapping.dep_concept] if mapping.dep_concept else DEP_CONCEPTS)
            m.assumptions.append("Maintenance capex assumed equal to depreciation (research_rules.md).")
        m.inputs = parts + [mc]
        for i in parts:
            if "treated as $0" in (i.note or ""):
                m.assumptions.append(f"{i.name}: {i.note.split('; ')[-1]} (research_rules.md).")
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


    # ------------------------------------------------------------ standing decisions
    def _apply_decisions(self, decisions, ni: Input, m: Metric) -> list[Input]:
        from .decisions import DEVIATION_ALARM, MIN_HISTORY_YEARS, SIZE_ALARM  # noqa: PLC0415
        out: list[Input] = []
        base = self._alarm_base(ni) if ni.value is not None else None
        anchor = self.ttm.current_q or self.ttm.annual
        for d in decisions.items:
            ttm = self.flow(d.name, d.concepts, displayed=True)
            if ttm.value is None and not self._present_anywhere(d.concepts):
                continue          # line not reported by this company in these filings: nothing to apply
            if d.treatment in {"exclude", "keep"}:
                if ttm.value is not None:
                    verb = "left out of owner earnings" if d.treatment == "exclude" else "kept in profit as reported"
                    m.assumptions.append(f"{d.name}: {verb} by Shubhansh's standing decision "
                                         f"(this period's cash-flow line {fmt_money(ttm.value)}).")
                continue
            if ttm.value is None:
                out.append(Input(f"Decided ({d.treatment}): {d.name}", None, note=ttm.note or f"{d.name}: not found"))
                continue
            series = self.annual_series(d.concepts, d.years) if d.treatment in {"normalize", "as_reported"} else []
            avg = sum(x.displayed_value for _, x, _ in series) / len(series) if series else None
            hist = ", ".join(f"{y}: {fmt_money(-x.displayed_value if d.treatment == 'normalize' else x.displayed_value)}"
                             for y, x, _ in series)
            hist_cites = [self.cite(f, x) for _, x, f in series]
            if d.treatment == "normalize":
                if len(series) < max(d.years, MIN_HISTORY_YEARS):
                    have = {y for y, _, _ in series}
                    last = self.ttm.annual.period_end.year
                    need = [y for y in range(last - d.years + 1, last + 1) if y not in have]
                    out.append(Input(f"Decided ({d.years}-yr average): {d.name}", None,
                                     note=(f"{d.name}: the decided {d.years}-year average needs fiscal years "
                                           f"{', '.join(map(str, need))}; add the 10-K covering them to the ticker's history/ "
                                           f"folder (each 10-K holds 3 years)")))
                    continue
                value = ttm.value - avg
                how = (f"this period's effect on profit {fmt_money(-ttm.value)} taken out; {len(series)}-year average effect "
                       f"{fmt_money(-avg)} used instead ({hist})")
                out.append(Input(f"Decided ({len(series)}-yr average): {d.name}", value, how, ttm.citations + hist_cites,
                                 note="standing decision"))
            else:   # remove or as_reported: include the cash-flow line as reported
                label = "removed (non-cash)" if d.treatment == "remove" else "as reported"
                how = ttm.how + (f"; {len(series)}-year history: {hist}" if series else "")
                out.append(Input(f"Decided ({label}): {d.name}", ttm.value, how, ttm.citations + hist_cites,
                                 note="standing decision"))
            if base is None:
                continue
            if d.alarm == "size" and abs(ttm.value) > SIZE_ALARM * base:
                m.alarms.append(f"unusually large {d.name}: {fmt_money(ttm.value)} this period is "
                                f"{abs(ttm.value) / base:.0%} of the alarm base (alarm at {SIZE_ALARM:.0%})")
            if d.alarm == "deviation" and avg is not None and abs(ttm.value - avg) > DEVIATION_ALARM * base:
                sign = -1 if d.treatment == "normalize" else 1
                m.alarms.append(f"{d.name} breaks from its {len(series)}-year history: {fmt_money(sign * ttm.value)} this "
                                f"period vs average {fmt_money(sign * avg)} (gap {abs(ttm.value - avg) / base:.0%} of the "
                                f"alarm base; alarm at {DEVIATION_ALARM:.0%})")
        if decisions.items:
            m.assumptions.append(f"Standing decisions applied from {anchor.path.parent.parent.name}/assumptions.md "
                                 f"(alarm base = larger of |net income| and 1% of shareholders' equity).")
        return out

    def _present_anywhere(self, concepts: list[str]) -> bool:
        return any(x.concept in concepts for f in self.ttm.used() for x in f.facts)


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
