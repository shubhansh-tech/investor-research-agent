"""The orchestrator: one research run for one ticker.

PRD Q13 loop, in code order:
  OBSERVE  preflight -> filings -> EDGAR list -> news -> baseline/thesis
  DECIDE   stop early on anything missing (NEEDS INFORMATION); ask the model for judgment
  ACT      calculator computes ROE and Owner Earnings Yield from the model's line-item choices
  CHECK    validator; one regeneration for model-output problems
  STOP     return exactly one review row
Fresh context every run and every ticker: nothing is carried over except what is
read from files (fetch logs, analysis.xlsx baseline, thesis note).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import config as C
from . import storage
from .calc import Calculator, Mapping, Metric, balance_check, fmt_money, pct
from .filings import (FilingRow, edgar_list_live, edgar_list_snapshot, find_new_filings, load_filings,
                      read_filing_list, select_ttm, ticker_mismatches)
from .news import (NewsItem, detect_injection, detect_material, event_filing_flags, event_filings_as_news,
                   load_synthetic_news)
from .prompts import SYSTEM, build_user_prompt
from .validator import check_citations, check_model_output, check_sources

READY, NEEDS_INFO, REVIEW_FIRST = "READY", "NEEDS INFORMATION", "REVIEW FIRST"
TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


@dataclass
class ReviewRow:
    run_id: str
    ticker: str
    as_of: str
    test_mode: bool
    status: str = READY
    status_reasons: list[str] = field(default_factory=list)
    review_first: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    what_changed: list[str] = field(default_factory=list)
    roe: Metric | None = None
    oey: Metric | None = None
    baseline_roe: float | None = None
    baseline_oey: float | None = None
    news: list[dict] = field(default_factory=list)
    embedded_instructions: list[dict] = field(default_factory=list)
    brief: str = ""
    thesis_check: str | None = None
    checks: list[str] = field(default_factory=list)          # passed checks (shown to reviewer)
    ttm_mode: str = ""
    filings_used: list[str] = field(default_factory=list)
    mapping_reasons: dict = field(default_factory=dict)
    one_time_items: list[dict] = field(default_factory=list)
    price: float | None = None
    model: str = ""
    live_calls: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)            # what the agent did, step by step

    def finalize_status(self) -> None:
        if self.missing:
            self.status = NEEDS_INFO
        elif self.review_first:
            self.status = REVIEW_FIRST
        else:
            self.status = READY

    def to_record(self) -> dict:
        def sup(m):
            if m is None:
                return ""
            lines = [m.formula] + [f"{i.name}: {fmt_money(i.value) if i.name != 'Share count' else f'{i.value:,.0f}'}"
                                   f" | {i.how} | " + "; ".join(c.short() for c in i.citations) for i in m.inputs]
            return "\n".join(lines + m.assumptions + m.missing)

        def inp(m, name):
            if m is None:
                return None
            return next((i.value for i in m.inputs if i.name == name), None)

        roe_v = self.roe.value if self.roe else None
        oey_v = self.oey.value if self.oey else None
        return {
            "run_id": self.run_id, "date_time": self.as_of, "ticker": self.ticker, "sector": "",
            "status": self.status, "roe": roe_v, "roe_flag": (self.roe.flag if self.roe else "withheld"),
            "ttm_net_income": inp(self.roe, "TTM net income"), "average_equity": inp(self.roe, "Average equity"),
            "roe_supporting_information": sup(self.roe), "owner_earnings_yield": oey_v,
            "owner_earnings": inp(self.oey, "Owner earnings"), "price": self.price,
            "share_count": inp(self.oey, "Share count"), "market_cap": inp(self.oey, "Market cap"),
            "owner_earnings_yield_supporting_information": sup(self.oey), "provisional": "N",
            "test_mode": "Y" if self.test_mode else "N", "what_changed": " | ".join(self.what_changed),
            "news_labels": " | ".join(f"{n['id']} {n.get('impact', '')}: {n['title']}" for n in self.news),
            "missing_information": " | ".join(self.missing), "agent_brief": self.brief,
            "shubhansh_brief": None, "reviewer_decision": "UNREVIEWED", "reviewer_input": None, "ask_answer": None,
        }


def parse_overrides(feedback: str | None) -> dict:
    """Assumption overrides Shubhansh can give in Reject feedback, e.g.
    'use maintenance capex of $150M'. Only assumptions can be overridden, never reported figures."""
    out = {}
    if not feedback:
        return out
    m = re.search(r"maintenance\s+capex\D{0,20}\$?\s*([\d,.]+)\s*(m|mm|million|b|bn|billion|k|thousand)?\b", feedback, re.I)
    if m:
        v = float(m[1].replace(",", ""))
        unit = (m[2] or "m").lower()
        v *= 1e9 if unit.startswith("b") else 1e3 if unit.startswith(("k", "t")) else 1e6
        out["maintenance_capex"] = v
    return out


def read_assumptions(tdir: Path) -> tuple[dict, str | None]:
    """<TICKER>/assumptions.md is written by Shubhansh (read-only for the agent). It holds
    standing judgment calls, e.g. a maintenance-capex figure when the company does not
    disclose depreciation. Line format: 'maintenance_capex_ttm: $150M'."""
    p = tdir / C.ASSUMPTIONS_FILE
    if not p.exists():
        return {}, None
    text = p.read_text(encoding="utf-8")
    out = {}
    m = re.search(r"maintenance_capex_ttm\s*:\s*\$?\s*([\d,.]+)\s*(m|mm|million|b|bn|billion)?", text, re.I)
    if m:
        v = float(m[1].replace(",", ""))
        v *= 1e9 if (m[2] or "m").lower().startswith("b") else 1e6
        out = {"maintenance_capex": v, "maintenance_capex_source": f"{tdir.name}/{C.ASSUMPTIONS_FILE}"}
    return out, text[:3000]


def preflight(root: Path, ticker: str, test_mode: bool) -> list[str]:
    t = root / ticker
    miss = []
    if not (root / C.RULES_FILE).exists():
        miss.append(f"{C.RULES_FILE} (shared research rules) in the data folder")
    if not t.is_dir():
        miss += [f"folder {ticker}/",
                 f"{ticker}/filings/ with the latest 10-K, the latest 10-Q and the prior-year same-quarter 10-Q "
                 f"(plus Item 2.02/4.02 8-Ks)",
                 f"{ticker}/{C.FETCH_LOG_10KQ} and {ticker}/{C.FETCH_LOG_8K} (EDGAR exports)"]
        if test_mode:
            miss += [f"{ticker}/{C.SNAPSHOT_DIR}/ (saved EDGAR filing lists)", f"{ticker}/{C.NEWS_DIR}/ (synthetic news)"]
        return miss
    fdir = t / "filings"
    if not fdir.is_dir() or not any(p.suffix.lower() in {".htm", ".html", ".xhtml"} for p in fdir.glob("*")):
        miss.append(f"{ticker}/filings/ with the latest 10-K and 10-Qs (inline-XBRL .htm files)")
    for log in (C.FETCH_LOG_10KQ, C.FETCH_LOG_8K):
        if not (t / log).exists():
            miss.append(f"{ticker}/{log} (EDGAR export)")
    if test_mode:
        if not (t / C.SNAPSHOT_DIR).is_dir():
            miss.append(f"{ticker}/{C.SNAPSHOT_DIR}/ (test mode never calls live EDGAR)")
        if not (t / C.NEWS_DIR).is_dir():
            miss.append(f"{ticker}/{C.NEWS_DIR}/ (test mode never searches live news)")
    return miss


def run_research(ticker: str, price: float | None, data_root: Path | str = C.DEFAULT_DATA_ROOT, *,
                 test_mode: bool = True, as_of: date | None = None, feedback: str | None = None,
                 llm=None, save: bool = True, ledger_root: Path | str | None = None) -> ReviewRow:
    root = Path(data_root)
    ledger = Path(ledger_root) if ledger_root else root   # where analysis.xlsx lives
    ticker = (ticker or "").strip().upper()
    as_of = as_of or date.today()
    row = ReviewRow(uuid.uuid4().hex[:10], ticker, f"{as_of.isoformat()} {datetime.now().strftime('%H:%M')} ET", test_mode, price=price)
    tr = row.trace.append

    def finish(save_row: bool = True) -> ReviewRow:
        row.finalize_status()
        if save and save_row and (root / ticker).is_dir():
            storage.append(ledger / ticker, row.to_record())
        return row

    # ---------------- OBSERVE: inputs and preflight
    if not TICKER_RE.match(ticker):
        row.missing.append(f"a valid ticker (got '{ticker}')")
        return finish(False)
    if price is None or price <= 0:
        row.missing.append("a current share price greater than zero")
    miss = preflight(root, ticker, test_mode)
    tr(f"Preflight: {'all required folders and files present' if not miss else str(len(miss)) + ' item(s) missing'}")
    if miss:
        row.missing += miss
        return finish(False)
    tdir = root / ticker

    filings, read_errors = load_filings(tdir)
    tr(f"Read {len(filings)} filing(s) from {ticker}/filings/")
    row.missing += read_errors
    bad = ticker_mismatches(ticker, filings)
    if bad:
        row.missing += [f"remove or replace: {b}" for b in bad]
        tr("Ticker check failed; stopped before any calculation")
        return finish()
    row.checks.append(f"All {len(filings)} filings belong to {ticker} (cover-page trading symbol)")

    log_kq = read_filing_list(tdir / C.FETCH_LOG_10KQ)
    log_8k = read_filing_list(tdir / C.FETCH_LOG_8K)
    try:
        edgar = edgar_list_snapshot(tdir) if test_mode else edgar_list_live(ticker, row.live_calls)
        tr(f"EDGAR filing list: {len(edgar)} filings ({'saved TEST snapshot' if test_mode else 'live sec.gov'})")
    except Exception as e:  # noqa: BLE001
        row.missing.append(f"EDGAR lookup failed ({e}); rerun when sec.gov is reachable")
        return finish()
    if test_mode and not edgar:
        row.missing.append(f"{ticker}/{C.SNAPSHOT_DIR}/ has no filing list files")
        return finish()
    new = find_new_filings(edgar, log_kq, log_8k, as_of)
    if new.must_download:
        for r in new.must_download:
            row.missing.append(f"download new filing {r.form} filed {r.filing_date} (accession {r.accession}) "
                               f"and add it to your fetch log: {r.url}")
        tr("New filing on EDGAR not yet saved; nothing recalculated")
        return finish()
    row.checks.append("No required filing on EDGAR is missing from the fetch logs (accession-number match)")

    ttm = select_ttm(filings, as_of)
    row.ttm_mode = ttm.mode
    row.filings_used = [f"{f.form} period ended {f.period_end} ({f.path.name})" for f in ttm.used()]
    if ttm.problems:
        row.missing += ttm.problems
        row.roe = Metric("ROE", None, flag="withheld", missing=ttm.problems)
        row.oey = Metric("Owner Earnings Yield", None, flag="withheld", missing=ttm.problems)
        tr("TTM filings incomplete; metrics withheld")
        return finish()
    tr(f"TTM method: {ttm.mode}")
    for f in ttm.used():
        ok, msg = balance_check(f, f.period_end)
        (row.checks if ok else row.missing).append(("Accounting check passed: " if ok else "Accounting check failed: ") + msg)

    # news
    if test_mode:
        news, probs = load_synthetic_news(tdir)
        row.missing += probs
    else:
        news = []
        tr("Live news search is post-MVP; reading EDGAR event filings only")
    news += event_filings_as_news(new.news_filings)
    for r in new.news_filings:
        for flag in event_filing_flags(r):
            row.review_first.append(f"{flag}: {r.form} filed {r.filing_date}")
    for n in news:
        for ev in detect_material(n.title + " " + n.body):
            row.review_first.append(f"{ev} ({n.id}: {n.title})")
        inj = detect_injection(n.body)
        if inj:
            row.embedded_instructions.append({"id": n.id, "quote": inj, "by": "code detector"})
    tr(f"News items read: {len(news)}")

    base = storage.baseline(ledger / ticker, test_mode)
    standing, assumptions_text = read_assumptions(tdir)
    thesis_p = tdir / C.THESIS_FILE
    thesis = thesis_p.read_text(encoding="utf-8")[:3000] if thesis_p.exists() else None
    if base:
        row.baseline_roe = base.get("roe")
        row.baseline_oey = base.get("owner_earnings_yield")

    # ---------------- DECIDE: model judgment
    anchor = ttm.current_q or ttm.annual
    cf = anchor.cash_flow_facts(anchor.period_end, anchor.ytd_start())
    if not cf:  # fallback: any ~1-year cash-flow context ending at the period end
        cf = [f for f in anchor.facts if f.section.endswith("Cash Flows") and not f.context.instant
              and f.context.end == anchor.period_end and not f.context.has_dimensions
              and 330 <= (f.context.end - f.context.start).days <= 380]
    cash_cands = {}
    for f in cf:
        if f.concept not in cash_cands:
            cash_cands[f.concept] = {"concept": f.concept, "label": f.label, "displayed_value_usd": f.displayed_value}
    dep_cands = {}
    for f in anchor.facts:
        if re.search(r"Depreciation|Amortization", f.concept) and not f.context.has_dimensions and not f.context.instant \
                and f.context.end == anchor.period_end and f.concept not in dep_cands:
            dep_cands[f.concept] = {"concept": f.concept, "label": f.label, "section": f.section, "value_usd": f.value}

    ctx = {
        "ticker": ticker, "as_of": as_of.isoformat(),
        "research_rules": (root / C.RULES_FILE).read_text(encoding="utf-8"),
        "ttm_method": ttm.mode, "filings_used": row.filings_used,
        "cash_flow_candidates": list(cash_cands.values()),
        "depreciation_candidates": list(dep_cands.values()),
        "news": [{"id": n.id, "date": n.date, "source": n.source, "title": n.title, "text": n.body[:2500]} for n in news],
        "material_events_detected_by_code": row.review_first,
        "baseline": {k: base.get(k) for k in ("date_time", "roe", "owner_earnings_yield", "agent_brief", "shubhansh_brief", "news_labels")} if base else None,
        "thesis_note": thesis,
        "shubhansh_assumptions": assumptions_text,
        "reviewer_feedback_for_this_rerun": feedback,
    }
    if llm is None:
        row.missing.append("AI model not configured (set ANTHROPIC_API_KEY)")
        return finish()
    row.model = getattr(llm, "model", getattr(llm, "name", ""))
    out, errs = None, []
    for attempt in (1, 2):
        try:
            out = llm.complete_json(SYSTEM, build_user_prompt(ctx, errs if attempt == 2 else None))
            errs = check_model_output(out, set(cash_cands), set(dep_cands), {n.id for n in news})
        except Exception as e:  # noqa: BLE001
            errs = [f"model call or JSON parsing failed: {e}"]
        tr(f"Model attempt {attempt}: {'passed checks' if not errs else 'failed: ' + '; '.join(errs)[:300]}")
        if not errs:
            break
    if errs:
        row.missing.append("model output failed checks after one regeneration: " + "; ".join(errs))
        return finish()

    mp = out.get("mapping") or {}
    mapping = Mapping(mp.get("da_concept"), mp.get("dep_concept"), list(mp.get("other_non_cash") or []),
                      list(mp.get("working_capital") or []), mp.get("reasons") or {})
    row.mapping_reasons = mapping.reasons
    row.one_time_items = out.get("one_time_items") or []
    for item in row.one_time_items:
        if item.get("needs_judgment"):
            row.review_first.append(f"one-time item needs judgment: {item.get('concept_or_news_id')} ({item.get('why', '')})")
    labels = {n["id"]: n for n in out.get("news") or []}
    for n in news:
        lab = labels.get(n.id, {})
        ev = lab.get("material_event")
        if ev and ev != "null" and not any(ev in r for r in row.review_first):
            row.review_first.append(f"{ev} ({n.id}: {n.title})")
        row.news.append({"id": n.id, "title": n.title, "date": n.date, "source": n.source, "url": n.url,
                         "origin": n.origin, "text": n.body[:300], "impact": lab.get("impact", "uncertain"),
                         "causal_path": lab.get("causal_path", ""), "fact_or_inference": lab.get("fact_or_inference", "")})
    for e in out.get("embedded_instructions") or []:
        if not any(x["id"] == e.get("id") for x in row.embedded_instructions):
            row.embedded_instructions.append({"id": e.get("id"), "quote": e.get("quote", ""), "by": "model"})
    if row.embedded_instructions:
        row.review_first.insert(0, "instructions embedded in content were ignored: " +
                                "; ".join(f"{e['id']}: \"{e['quote'][:120]}\"" for e in row.embedded_instructions))
    row.what_changed = list(out.get("what_changed") or [])[:3]
    row.brief = out.get("brief", "")
    row.thesis_check = out.get("thesis_check")

    # ---------------- ACT: calculator
    calc = Calculator(ttm, log_kq + log_8k)
    row.roe = calc.roe()
    overrides = {**standing, **parse_overrides(feedback)}   # this rerun's feedback wins over the standing file
    if "maintenance_capex" in parse_overrides(feedback):
        overrides["maintenance_capex_source"] = "Reject feedback on this rerun"
    row.oey = calc.owner_earnings_yield(mapping, price, overrides)
    tr(f"Calculator: ROE {pct(row.roe.value) if row.roe.value is not None else row.roe.flag}, "
       f"Owner Earnings Yield {pct(row.oey.value) if row.oey.value is not None else row.oey.flag}")
    for m in (row.roe, row.oey):
        row.missing += [f"{m.name} withheld: {x}" for x in m.missing]

    # ---------------- CHECK: validator
    by_name = {f.path.name: f for f in filings}
    cerr = check_citations(row.roe, by_name) + check_citations(row.oey, by_name)
    serr = check_sources(row, test_mode, row.live_calls)
    if not cerr:
        row.checks.append("Every input traces to a cited filing fact with the same value")
    if not serr:
        row.checks.append("Sources: no test/live mixing" + ("" if test_mode else "; all links from approved domains"))
    row.missing += cerr + serr
    row.checks.append("No buy/sell or price-target language in the brief")
    tr(f"Validator: {len(cerr) + len(serr)} problem(s)")
    return finish()


def run_many(tickers_prices: list[tuple[str, float | None]], **kw) -> list[ReviewRow]:
    """Each ticker gets a fresh, independent run (no content carried across tickers)."""
    return [run_research(t, p, **kw) for t, p in tickers_prices]
