"""News items and the deterministic safety detectors.

Test mode: read invented articles from <TICKER>/synthetic-news_TEST_only/.
Daily use (MVP): live news search is post-MVP; the agent reads EDGAR event filings
(other 8-Ks, Form 4s, late-filing notices) found by the new-filing check.

The keyword detectors below are a safety net that does not depend on the AI: if an
article says "lowers full-year guidance", the row is REVIEW FIRST even if the model
missed it. The model adds labels and reasoning on top.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config as C
from .filings import FilingRow


@dataclass
class NewsItem:
    id: str
    title: str
    source: str
    date: str
    url: str
    body: str
    origin: str          # "synthetic-test" | "edgar-event"
    path: str = ""

    def as_prompt(self) -> str:
        return f"[{self.id}] {self.date} | {self.source} | {self.title}\n{self.body[:2500]}"


def load_synthetic_news(tdir: Path) -> tuple[list[NewsItem], list[str]]:
    items, problems = [], []
    folder = tdir / C.NEWS_DIR
    for i, p in enumerate(sorted(folder.glob("*")), start=1):
        if p.suffix.lower() not in {".md", ".html", ".htm", ".txt"}:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if not text.lstrip().startswith(C.SYNTHETIC_TAG):
            problems.append(f"{p.name} is in the test-news folder but does not start with {C.SYNTHETIC_TAG}; ignored")
            continue
        head, _, body = text.partition("\n---")
        meta = dict(re.findall(r"^(\w+):\s*(.+)$", head, re.M))
        body = re.sub(r"<[^>]+>", " ", body).strip()
        items.append(NewsItem(f"N{i}", meta.get("title", p.stem), meta.get("source", "synthetic"),
                              meta.get("date", ""), f"{C.NEWS_DIR}/{p.name}", body, "synthetic-test", str(p)))
    return items, problems


def event_filings_as_news(rows: list[FilingRow]) -> list[NewsItem]:
    out = []
    for i, r in enumerate(rows, start=1):
        out.append(NewsItem(f"F{i}", f"{r.form}: {r.description}".strip(), "SEC EDGAR",
                            r.filing_date.isoformat() if r.filing_date else "", r.url,
                            f"{r.form} filed {r.filing_date}. {r.description}", "edgar-event"))
    return out


# ------------------------------------------------------------- detectors
MATERIAL_PATTERNS = {
    "guidance cut": re.compile(r"\b(lower|lowers|lowered|cut|cuts|reduc\w*|slash\w*|withdr\w*)\b[^.]{0,60}\b(guidance|outlook|forecast)\b", re.I),
    "going-concern warning": re.compile(r"going[- ]concern", re.I),
    "restatement": re.compile(r"\brestat(e|es|ed|ement)\b|non-reliance|item\s*4\.02", re.I),
    "auditor change": re.compile(r"item\s*4\.01|\b(dismiss\w*|resign\w*|replac\w*)\b[^.]{0,50}\b(auditor|accounting firm)\b", re.I),
    "late-filing notice": re.compile(r"\bNT\s*10-[KQ]\b|notification of late filing|unable to file[^.]{0,40}timely", re.I),
    "large insider sale": re.compile(r"\b(sold|sells|sale of)\b[^.]{0,60}\b(shares|stock)\b[^.]{0,80}\b(director|officer|ceo|cfo|chief|insider)\b|\binsider\b[^.]{0,30}\b(sold|sale)\b", re.I),
}
INJECTION_PATTERN = re.compile(
    r"(ignore|disregard|override|forget)\s+(all\s+|your\s+|any\s+|the\s+|previous\s+|prior\s+)*(rules|instructions|guidelines|prompt)"
    r"|recommend\s+(buying|selling|that you buy|that you sell)|\bsystem prompt\b|you are now\b|new instructions:",
    re.I)


def detect_material(text: str) -> list[str]:
    return [name for name, pat in MATERIAL_PATTERNS.items() if pat.search(text or "")]


def detect_injection(text: str) -> str | None:
    m = INJECTION_PATTERN.search(text or "")
    if not m:
        return None
    s = max(0, m.start() - 40)
    return (text[s:m.end() + 60]).replace("\n", " ").strip()


def event_filing_flags(r: FilingRow) -> list[str]:
    flags = []
    form = r.form.upper()
    for item, label in C.MATERIAL_8K_ITEMS.items():
        if form.startswith("8-K") and item in r.items:
            flags.append(label)
    if form in C.LATE_FILING_FORMS:
        flags.append(f"late-filing notice ({form})")
    return flags
