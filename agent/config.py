"""Settings and fixed rules. Nothing in here is decided by the AI."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = REPO_ROOT / "data"

SYNTHETIC_TAG = "SYNTHETIC_TEST_DATA----TAG"
TEST_ONLY_MARK = "_TEST_only"
RULES_FILE = "research_rules.md"

FETCH_LOG_10KQ = "10-K-10-Q_fetch_log.xlsx"
FETCH_LOG_8K = "8-K_fetch_log.xlsx"
SNAPSHOT_DIR = "edgar_snapshot_TEST_only"
SNAPSHOT_10KQ = "10-K-10-Q_EDGAR_filing_list.xlsx"
SNAPSHOT_8K = "8-K_EDGAR_filing_list.xlsx"
NEWS_DIR = "synthetic-news_TEST_only"
ANALYSIS_FILE = "analysis.xlsx"
THESIS_FILE = "thesis_note.md"
ASSUMPTIONS_FILE = "assumptions.md"

# Filings Shubhansh must download himself (PRD Q14 filing rules)
REQUIRED_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
REQUIRED_8K_ITEMS = {"2.02", "4.02"}
# Read as news (never downloaded)
MATERIAL_8K_ITEMS = {"4.01": "auditor change (8-K Item 4.01)", "4.02": "restatement (8-K Item 4.02)"}
LATE_FILING_FORMS = {"NT 10-K", "NT 10-Q"}

APPROVED_DOMAINS = [
    "sec.gov", "investor.chubb.com", "news.chubb.com", "chubb.com", "quantumcomputinginc.com",
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "barrons.com",
    "apnews.com", "marketwatch.com", "businesswire.com", "prnewswire.com", "globenewswire.com",
]

MAX_BRIEF_WORDS = 200
MAX_REVIEWER_CHARS = 500
NEWS_LOOKBACK_DAYS = 30

# Model settings come from environment / Streamlit secrets, never from code.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "investor-research-agent (contact: set SEC_USER_AGENT)")
