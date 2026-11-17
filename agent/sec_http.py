"""Polite access to SEC's free JSON services (EDGAR), shared by every caller.

Teaching note
-------------
SEC asks automated tools to (1) identify themselves with a name and contact email in the
User-Agent header and (2) stay under 10 requests per second. Tools that don't are slowed down or
refused ("403 Forbidden" / "429 Too Many Requests"). This module:
  * sends the owner's SEC_USER_AGENT, read fresh on every request (not frozen at start-up),
  * remembers answers for a while (the all-tickers list for a day, a company's filing list for a
    few minutes), so a session does not ask SEC the same question again and again,
  * on 429/503, waits as long as SEC asks (Retry-After) and tries again, at most 3 times,
  * spaces requests at least 0.15 s apart (under SEC's 10 per second).
A failure after the retries is raised with a plain explanation; the caller stops at NEEDS
INFORMATION, as before (a failed fetch is never replaced by guessed data).
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

from . import config as C

TTL_TICKERS = 24 * 3600          # SEC's list of all tickers changes rarely
TTL_DEFAULT = 300                # a company's filing list: 5 minutes
ATTEMPTS = 3
MIN_GAP = 0.15

_cache: dict[str, tuple[float, object]] = {}
_lock = threading.Lock()
_last_call = [0.0]


class SecUnavailable(RuntimeError):
    pass


def user_agent() -> str:
    return os.getenv("SEC_USER_AGENT") or C.SEC_USER_AGENT


def get_json(url: str, log: list | None = None, ttl: float | None = None):
    ttl = TTL_TICKERS if url.endswith("company_tickers.json") else (TTL_DEFAULT if ttl is None else ttl)
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < ttl:
            return hit[1]
    if log is not None:
        log.append(url)
    for attempt in range(1, ATTEMPTS + 1):
        with _lock:
            wait = MIN_GAP - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            with _lock:
                _cache[url] = (time.time(), data)
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < ATTEMPTS:
                try:
                    delay = float(e.headers.get("Retry-After", "")) if e.headers else 0.0
                except ValueError:
                    delay = 0.0
                time.sleep(min(max(delay, 2.0 * attempt), 15.0))
                continue
            if e.code == 429:
                raise SecUnavailable("SEC's server asked the app to slow down (too many requests reached it from "
                                     "this app's shared server). Wait a few minutes and run again.") from e
            if e.code == 403:
                raise SecUnavailable("SEC refused the request (403). Check that SEC_USER_AGENT in the app's "
                                     "Secrets has your name and email, e.g. 'Jane Doe jane@example.com'.") from e
            raise SecUnavailable(f"SEC EDGAR returned an error ({e.code}). Try again in a few minutes.") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < ATTEMPTS:
                time.sleep(2.0 * attempt)
                continue
            raise SecUnavailable(f"SEC EDGAR could not be reached ({getattr(e, 'reason', e)}). "
                                 "Try again in a few minutes.") from e
    raise SecUnavailable("SEC EDGAR could not be reached. Try again in a few minutes.")
