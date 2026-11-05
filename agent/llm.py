"""The only place the AI model is called.

The model gets read-only context (rules, line-item candidates, news, baseline) and
returns JSON. It has no tools that can act on the world: no trading, no messaging,
no file writes. `MockLLM` is a deterministic stand-in used by unit tests and for
running the app without an API key.
"""
from __future__ import annotations

import json
import os
import re

from . import config as C


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m[1]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise LLMError("model did not return JSON")
    body = text[start:end + 1]
    try:
        return json.loads(body)
    except json.JSONDecodeError as first:
        fixed = repair_json(body)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            near = body[max(0, first.pos - 60):first.pos + 40].replace("\n", " ")
            raise LLMError(f"{first.msg} at char {first.pos}; near: ...{near}...") from first


_MISSING_COMMA = re.compile(r'(["}\]]|\d|true|false|null)(\s*\n\s*)(["{\[])')
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def repair_json(body: str) -> str:
    """Fix the two slips the model makes most: a missing comma between items written on
    separate lines, and a trailing comma before a closing bracket. JSON strings cannot
    contain raw line breaks, so a line break always sits between tokens and inserting a
    comma there never changes a value."""
    body = _MISSING_COMMA.sub(r"\1,\2\3", body)
    return _TRAILING_COMMA.sub(r"\1", body)


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        import anthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or C.ANTHROPIC_MODEL

    def complete_json(self, system: str, user: str, max_tokens: int = 4000) -> dict:
        resp = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _extract_json(text)

    def complete_text(self, system: str, user: str, max_tokens: int = 800) -> str:
        resp = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()

    def search_news(self, system: str, user: str, allowed_domains: list[str], max_uses: int = 3,
                    max_tokens: int = 3000) -> tuple[dict, list[dict], int]:
        """Anthropic's server-side web search, limited by the API to allowed_domains.
        Returns (JSON answer, every search result the API returned, searches used).
        The model's only tool here is web search: it cannot act on anything."""
        tool = {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses,
                "allowed_domains": allowed_domains}
        messages = [{"role": "user", "content": user}]
        results, texts, used = [], [], 0
        for _ in range(3):        # a long search turn may pause; continue it at most twice
            resp = self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                               messages=messages, tools=[tool])
            usage = getattr(getattr(resp, "usage", None), "server_tool_use", None)
            used += int(getattr(usage, "web_search_requests", 0) or 0)
            for b in resp.content:
                kind = getattr(b, "type", "")
                if kind == "text":
                    texts.append(b.text)
                elif kind == "web_search_tool_result":
                    content = getattr(b, "content", None)
                    if isinstance(content, list):
                        results += [{"url": r.url, "title": getattr(r, "title", ""),
                                     "page_age": getattr(r, "page_age", None)} for r in content]
                    elif content is not None and getattr(content, "error_code", None):
                        raise LLMError(f"news search failed: {content.error_code}")
            if getattr(resp, "stop_reason", "") != "pause_turn":
                break
            messages = messages + [{"role": "assistant", "content": resp.content}]
        return _extract_json("".join(texts)), results, used


class MockLLM:
    """Deterministic offline stand-in. Picks obvious line items and writes a
    templated brief, so the pipeline can be tested without a model."""
    name = "mock"

    def __init__(self, ctx_hook=None):
        self.ctx_hook = ctx_hook
        self.last_payload: dict | None = None

    def complete_json(self, system: str, user: str, max_tokens: int = 4000) -> dict:
        if "BRIEF_CONTEXT_JSON:" in user:
            ctx = json.loads(user.split("BRIEF_CONTEXT_JSON:", 1)[1])
            roe = (ctx.get("roe") or {}).get("value")
            oey = (ctx.get("owner_earnings_yield") or {}).get("value")
            changed = [{"text": f"Mock brief: ROE {roe} and Owner Earnings Yield {oey} as computed by code."
                        if roe and oey else "Mock brief: metrics are withheld; see missing information.",
                        "basis": "fact"}]
            news = [{"text": f"[{n['id']}] {n['title'][:80]} (impact {n.get('impact')}).", "basis": "fact"}
                    for n in ctx.get("news") or []][:3]
            return {"what_changed": changed, "news": news, "check": [], "thesis_check": None}
        payload = json.loads(user.split("CONTEXT_JSON:", 1)[1])
        self.last_payload = payload
        cands = payload["cash_flow_candidates"]
        nc, wc = [], []
        for c in cands:
            k = c["concept"]
            if "ShareBasedCompensation" in k or "DeferredIncomeTax" in k or "AssetImpairment" in k:
                nc.append(k)
            elif "IncreaseDecrease" in k:
                wc.append(k)
        da = next((c["concept"] for c in cands if "Depreciation" in c["concept"]), None)
        dep = next((c["concept"] for c in payload["depreciation_candidates"] if c["concept"].endswith(":Depreciation")), None)
        news = []
        for n in payload["news"]:
            low = n["text"].lower()
            impact = "negative" if any(w in low for w in ("lower", "cut", "loss", "decline")) else (
                "positive" if any(w in low for w in ("beat", "raise", "record", "exceed")) else "uncertain")
            news.append({"id": n["id"], "impact": impact, "causal_path": "Keyword-based placeholder (mock model).",
                         "fact_or_inference": "reported fact", "material_event": None})
        return {
            "mapping": {"da_concept": da, "dep_concept": dep, "other_non_cash": nc, "working_capital": wc,
                        "reasons": {"mock": "deterministic mock mapping"}},
            "one_time_items": [],
            "news": news,
            "embedded_instructions": [],
        }

    def complete_text(self, system: str, user: str, max_tokens: int = 800) -> str:
        return "Mock answer: the model is not connected in this run."

    def search_news(self, system: str, user: str, allowed_domains: list[str], max_uses: int = 3,
                    max_tokens: int = 3000) -> tuple[dict, list[dict], int]:
        """The mock never reaches the internet: no live news, zero searches."""
        return {"items": [], "embedded_instructions": []}, [], 0


def get_llm(use_mock: bool = False, api_key: str | None = None):
    if use_mock:
        return MockLLM()
    return AnthropicLLM(api_key=api_key)
