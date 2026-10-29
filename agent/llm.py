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
    return json.loads(text[start:end + 1])


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


class MockLLM:
    """Deterministic offline stand-in. Picks obvious line items and writes a
    templated brief, so the pipeline can be tested without a model."""
    name = "mock"

    def __init__(self, ctx_hook=None):
        self.ctx_hook = ctx_hook
        self.last_payload: dict | None = None

    def complete_json(self, system: str, user: str, max_tokens: int = 4000) -> dict:
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
            "what_changed": ["Mock run: no model reasoning applied."],
            "brief": "Mock brief for testing the pipeline. Figures are computed by code from cited filings. "
                     "No model judgment was applied, so treat news labels as placeholders.",
            "thesis_check": None,
        }

    def complete_text(self, system: str, user: str, max_tokens: int = 800) -> str:
        return "Mock answer: the model is not connected in this run."


def get_llm(use_mock: bool = False, api_key: str | None = None):
    if use_mock:
        return MockLLM()
    return AnthropicLLM(api_key=api_key)
