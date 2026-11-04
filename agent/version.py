"""Which code version is running: the short git commit ID, as shown on GitHub.

Shown in the app sidebar and recorded in every scorecard, so a result can always be
traced to the exact code that produced it.
"""
from __future__ import annotations

import functools
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _from_git_files() -> tuple[str, str] | None:
    """Read .git directly, for hosts without the git command."""
    g = ROOT / ".git"
    try:
        head = (g / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1]
            p = g / ref
            if p.exists():
                sha = p.read_text().strip()
            else:
                sha = next(line.split()[0] for line in (g / "packed-refs").read_text().splitlines()
                           if line.endswith(ref))
        else:
            sha = head
        return sha[:7], ""
    except Exception:  # noqa: BLE001
        return None


@functools.lru_cache(maxsize=1)
def app_version() -> dict:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%h|%cs"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and "|" in out.stdout:
            sha, day = out.stdout.strip().split("|", 1)
            return {"commit": sha[:7], "date": day}
    except Exception:  # noqa: BLE001
        pass
    alt = _from_git_files()
    if alt:
        return {"commit": alt[0], "date": alt[1]}
    return {"commit": "unknown", "date": ""}


def label() -> str:
    v = app_version()
    return f"Version: {v['commit']}" + (f" ({v['date']})" if v["date"] else "")
