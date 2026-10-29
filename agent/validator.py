"""The validator: code checks that run on every row before Approve is possible.

Two kinds of failure:
  * model-output problems (bad JSON, unknown line item, >200 words, buy/sell
    language) -> the model gets ONE retry with the errors listed, then the row
    stops at NEEDS INFORMATION. No endless loops.
  * data problems (missing input, failed accounting check, uncited number,
    unapproved source, test/live mixing) -> NEEDS INFORMATION, metric withheld.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from . import config as C

TRADE_LANGUAGE = re.compile(
    r"\b(buy|buys|buying|sell|sells|selling|purchase (?:more )?shares|add to (?:the |your )?position|trim (?:the |your )?position|"
    r"price target|target price|overweight|underweight|accumulate|take profits?|strong buy|exit the position)\b", re.I)
ALLOWED_PHRASES = re.compile(
    r"insider sell\w*|sell-?off|selling,? general|sell-side|buy-?backs?|buy-side", re.I)

VALID_IMPACTS = {"positive", "negative", "mixed", "uncertain"}


def trade_language(text: str) -> list[str]:
    cleaned = ALLOWED_PHRASES.sub(" ", text or "")
    return sorted({m.group(0).lower() for m in TRADE_LANGUAGE.finditer(cleaned)})


def check_model_output(out: dict, cash_cands: set[str], dep_cands: set[str], news_ids: set[str]) -> list[str]:
    errs: list[str] = []
    mp = out.get("mapping") or {}
    if not isinstance(mp, dict):
        return ["'mapping' must be an object"]
    used: list[str] = []
    if mp.get("da_concept") and mp["da_concept"] not in cash_cands:
        errs.append(f"da_concept {mp['da_concept']} is not in cash_flow_candidates")
    if mp.get("dep_concept") and mp["dep_concept"] not in dep_cands:
        errs.append(f"dep_concept {mp['dep_concept']} is not in depreciation_candidates")
    for key in ("other_non_cash", "working_capital"):
        for c in mp.get(key) or []:
            if c not in cash_cands:
                errs.append(f"{key}: {c} is not in cash_flow_candidates")
            if re.search(r"NetIncome|ProfitLoss|PaymentsToAcquire", c):
                errs.append(f"{key}: {c} must not be included")
            used.append(c)
    if mp.get("da_concept"):
        used.append(mp["da_concept"])
    dups = {c for c in used if used.count(c) > 1}
    if dups:
        errs.append(f"concepts used more than once: {sorted(dups)}")
    brief = out.get("brief") or ""
    if not brief.strip():
        errs.append("brief is empty")
    if len(brief.split()) > C.MAX_BRIEF_WORDS:
        errs.append(f"brief has {len(brief.split())} words; limit is {C.MAX_BRIEF_WORDS}")
    texts = [brief, out.get("thesis_check") or ""] + list(out.get("what_changed") or [])
    texts += [n.get("causal_path", "") for n in out.get("news") or []]
    bad = trade_language(" ".join(texts))
    if bad:
        errs.append(f"contains trade/recommendation language: {bad}")
    labelled = set()
    for n in out.get("news") or []:
        if n.get("impact") not in VALID_IMPACTS:
            errs.append(f"news {n.get('id')}: impact must be one of {sorted(VALID_IMPACTS)}")
        labelled.add(n.get("id"))
    missing = news_ids - labelled
    if missing:
        errs.append(f"news items not labelled: {sorted(missing)}")
    return errs


def domain_ok(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in C.APPROVED_DOMAINS)


def check_sources(row, test_mode: bool, live_calls: list[str]) -> list[str]:
    """Test/live separation and approved domains."""
    errs = []
    urls = [c.url for m in (row.roe, row.oey) if m for i in m.inputs for c in i.citations if c.url]
    urls += [n["url"] for n in row.news if n.get("url")]
    if test_mode:
        if live_calls:
            errs.append(f"test mode made live calls: {live_calls}")
    else:
        for n in row.news:
            if C.TEST_ONLY_MARK in (n.get("url") or "") or n.get("origin") == "synthetic-test":
                errs.append(f"daily use cited test-only content: {n.get('url')}")
            if C.SYNTHETIC_TAG in (n.get("text") or ""):
                errs.append("daily use read an item carrying the synthetic test tag")
        for u in urls:
            if u.startswith("http") and not domain_ok(u):
                errs.append(f"citation from an unapproved domain: {u}")
    return errs


def check_citations(metric, filings_by_name: dict) -> list[str]:
    """Every cited number must exist in the cited filing with the same value."""
    errs = []
    if metric is None or metric.value is None:
        return errs
    derived = {"Average equity", "Owner earnings", "Market cap"}
    for inp in metric.inputs:
        if inp.name in derived or inp.note == "reviewer override":
            continue
        if not inp.citations:
            errs.append(f"{metric.name}: input '{inp.name}' has no citation")
            continue
        for c in inp.citations:
            f = filings_by_name.get(c.file)
            if f is None:
                errs.append(f"{metric.name}: cited file {c.file} was not read")
                continue
            ok = any(x.concept == c.concept and (abs(x.value - c.value) < 0.5 or abs(x.displayed_value - c.value) < 0.5)
                     for x in f.facts)
            if not ok:
                errs.append(f"{metric.name}: {c.concept} = {c.value:,.0f} not found in {c.file}")
    return errs
