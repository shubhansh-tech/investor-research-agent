"""Actions behind the buttons of the "Setup & filings" tab. Code only; no model is involved.

Teaching note
-------------
Every action that writes a file follows "show, then confirm": the app shows what it found or
understood, and only the owner's confirm click saves it. Uploaded filings get a strict check
(the right company, form and period, read from the filing's own cover-page tags) before they
are saved under the expected name, so a wrong file is never used silently.
Uploaded files are data, never instructions.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd

from . import config as C
from . import decisions as decisions_mod
from .ixbrl import parse_filing

MAX_FILING_BYTES = 60_000_000      # the largest 10-Ks are tens of MB
MAX_TEXT_BYTES = 200_000


def create_folder(root: Path, ticker: str) -> Path:
    tdir = root / ticker
    (tdir / "filings").mkdir(parents=True, exist_ok=True)
    return tdir


def save_logs(tdir: Path, guide) -> None:
    (tdir / C.FETCH_LOG_10KQ).write_bytes(guide.log_10kq)
    (tdir / C.FETCH_LOG_8K).write_bytes(guide.log_8k)


def log_table(data: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(data))
    for c in df.columns:                       # show dates as 2026-06-30, not 2026-06-30 00:00:00
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.date
    return df


def check_filing(data: bytes, expected, cik: int, ticker: str) -> tuple[bool, str]:
    """Strict check of an uploaded filing against the one expected (onboarding.Doc).
    Returns (ok, message). The message names exactly what is wrong."""
    if len(data) > MAX_FILING_BYTES:
        return False, "The file is larger than 60 MB; this is not a single filing."
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "upload.htm"
        p.write_bytes(data)
        try:
            f = parse_filing(p)
        except Exception as e:  # noqa: BLE001
            return False, f"The file could not be read as a filing ({e})."
    if not f.form or not f.period_end:
        return False, ("This file has no machine-readable cover page (document type and period). It is probably "
                       "the EDGAR viewer page instead of the filing: open the link given here, or remove "
                       "'ix?doc=/' from the address, and save again.")
    who = f.registrant or (f.trading_symbols[0] if f.trading_symbols else "another company")
    same_company = (f.cik and f.cik.lstrip("0") == str(cik)) or ticker.upper() in [s.upper() for s in f.trading_symbols]
    if not same_company:
        return False, (f"This is {who}'s {f.form} for the period ended {f.period_end}; "
                       f"{ticker}'s {expected.form} for the period ended {expected.period} is needed.")
    if f.form.replace("/A", "") != expected.form or f.period_end != expected.period:
        return False, (f"This is {ticker}'s {f.form} for the period ended {f.period_end}; "
                       f"the {expected.form} for the period ended {expected.period} is needed here.")
    return True, f"Correct: {ticker}'s {f.form} for the period ended {f.period_end}."


def save_filing(tdir: Path, expected, data: bytes) -> Path:
    p = tdir / "filings" / expected.file_name
    p.write_bytes(data)
    return p


def check_assumptions(data: bytes):
    """Read an uploaded assumptions.md the way the agent will. Returns (decisions, overrides, text, problems)."""
    from .pipeline import read_assumptions
    if len(data) > MAX_TEXT_BYTES:
        return None, {}, "", ["The file is larger than 200 KB; assumptions.md is a short text file."]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, {}, "", ["The file is not plain text (UTF-8). Save it as a .md or .txt text file."]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "assumptions.md").write_text(text)
        dec = decisions_mod.load(Path(d))
        overrides, _ = read_assumptions(Path(d))
    return dec, overrides, text, list(dec.problems)


def save_assumptions(tdir: Path, text: str) -> None:
    (tdir / "assumptions.md").write_text(text)
