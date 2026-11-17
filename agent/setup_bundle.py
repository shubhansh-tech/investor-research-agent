"""Download and restore the owner's setup as one .zip (the hosted app keeps files only for a session).

Teaching note
-------------
One .zip holds everything the owner can change: each ticker's folder (fetch logs, filings,
assumptions.md), the decision logs and the research rules. Test-only data (snapshots, synthetic
news, the fictional EXMP company) is left out: the app already has it, and test mode never
reads the owner's copy.

Restoring is "show, then confirm", and the .zip is treated as untrusted data: only known file
names in known places are restored (no paths that climb out of the folder, no links, no other
file types), with size limits. Anything else is listed as skipped.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C
from .setup_status import TEST_ONLY_TICKERS

TICKER = r"[A-Z][A-Z0-9.\-]{0,9}"
ALLOWED = [
    re.compile(rf"^tickers/({TICKER})/(10-K-10-Q_fetch_log(_previous)?\.xlsx|8-K_fetch_log(_previous)?\.xlsx|assumptions\.md)$"),
    re.compile(rf"^tickers/({TICKER})/(filings|history)/[A-Za-z0-9._\-]{{1,120}}\.html?$"),
    re.compile(rf"^decision_logs/({TICKER})/{re.escape(C.ANALYSIS_FILE)}$"),
    re.compile(r"^research_rules\.md$"),
]
IGNORED = {"manifest.json", "README.txt"}
MAX_ZIP_BYTES = 150_000_000
MAX_TOTAL_BYTES = 400_000_000
MAX_ENTRIES = 2000


def _ticker_files(tdir: Path):
    for p in sorted(tdir.rglob("*")):
        rel = p.relative_to(tdir)
        if p.is_file() and not p.is_symlink() and not any("_TEST_only" in part for part in rel.parts):
            yield p, rel


def make_bundle(root: Path, ledger: Path, version: str, created: str) -> bytes:
    buf = io.BytesIO()
    tickers = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for tdir in sorted(p for p in root.iterdir() if p.is_dir()):
            t = tdir.name
            if t in TEST_ONLY_TICKERS or not re.fullmatch(TICKER, t):
                continue
            tickers.append(t)
            for p, rel in _ticker_files(tdir):
                name = f"tickers/{t}/{rel.as_posix()}"
                if any(rx.match(name) for rx in ALLOWED):
                    z.write(p, name)
        for log in sorted(ledger.glob(f"*/{C.ANALYSIS_FILE}")) if ledger.is_dir() else []:
            z.write(log, f"decision_logs/{log.parent.name}/{C.ANALYSIS_FILE}")
        if (root / C.RULES_FILE).exists():
            z.write(root / C.RULES_FILE, C.RULES_FILE)
        z.writestr("manifest.json", json.dumps({"created": created, "app_version": version, "tickers": tickers}, indent=2))
        z.writestr("README.txt", "Pre-market Research Agent: your saved setup. Restore it on the Setup & filings tab.\n")
    return buf.getvalue()


@dataclass
class BundlePreview:
    ok: bool
    error: str = ""
    files: dict = field(default_factory=dict)        # ticker -> list of paths inside its folder
    logs: list = field(default_factory=list)         # tickers with a decision log
    rules: bool = False
    skipped: list = field(default_factory=list)
    created: str = ""


def inspect_bundle(data: bytes) -> BundlePreview:
    if len(data) > MAX_ZIP_BYTES:
        return BundlePreview(False, "The file is larger than 150 MB; this is not a saved setup.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return BundlePreview(False, "This is not a .zip file.")
    infos = z.infolist()
    if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
        return BundlePreview(False, "The .zip is too large to be a saved setup.")
    pv = BundlePreview(True)
    for i in infos:
        name = i.filename
        if i.is_dir() or name in IGNORED:
            if name == "manifest.json":
                try:
                    pv.created = json.loads(z.read(i)).get("created", "")
                except Exception:  # noqa: BLE001
                    pass
            continue
        is_link = (i.external_attr >> 16) & 0o170000 == 0o120000
        m = next((rx.match(name) for rx in ALLOWED if rx.match(name)), None)
        if is_link or m is None or ".." in name or name.startswith("/") or "\\" in name:
            pv.skipped.append(name)
            continue
        if name == C.RULES_FILE:
            pv.rules = True
        elif name.startswith("decision_logs/"):
            pv.logs.append(m.group(1))
        elif m.group(1) in TEST_ONLY_TICKERS:
            pv.skipped.append(name)
        else:
            pv.files.setdefault(m.group(1), []).append(name.split("/", 2)[2])
    if not (pv.files or pv.logs or pv.rules):
        return BundlePreview(False, "Nothing in this .zip looks like a saved setup from this app.", skipped=pv.skipped)
    return pv


def restore_bundle(data: bytes, root: Path, ledger: Path) -> BundlePreview:
    """Write the allowed files. Ticker files replace same-named files; decision logs are merged by run."""
    from .storage import load_upload
    pv = inspect_bundle(data)
    if not pv.ok:
        return pv
    z = zipfile.ZipFile(io.BytesIO(data))
    for t, rels in pv.files.items():
        for rel in rels:
            dest = (root / t / rel).resolve()
            if not str(dest).startswith(str((root / t).resolve())):
                continue                                   # belt and braces: never write outside the folder
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(f"tickers/{t}/{rel}"))
    for t in pv.logs:
        load_upload(ledger, z.read(f"decision_logs/{t}/{C.ANALYSIS_FILE}"))
    if pv.rules:
        (root / C.RULES_FILE).write_bytes(z.read(C.RULES_FILE))
    return pv
