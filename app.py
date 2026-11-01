"""Pre-market Research Agent: the review screen.

Run locally:   streamlit run app.py
The screen shows one review row per ticker. Approve records a review only:
no trade, order or brokerage tool exists anywhere in this codebase.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from agent import config as C
from agent import storage
from agent.calc import fmt_money, pct
from agent.llm import LLMError, get_llm
from agent.pipeline import NEEDS_INFO, READY, REVIEW_FIRST, run_research
from agent.prompts import ASK_SYSTEM
from evals.scenarios import build as build_scenario

st.set_page_config(page_title="Pre-market Research Agent", page_icon="📈", layout="wide")

# ---- secrets -> environment (never hard-coded)
for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "SEC_USER_AGENT", "APP_PASSCODE", "MAX_MODEL_CALLS_PER_SESSION"):
    try:
        if k in st.secrets and not os.getenv(k):
            os.environ[k] = str(st.secrets[k])
    except Exception:  # noqa: BLE001  (no secrets file locally is fine)
        pass

SPEC = yaml.safe_load((C.REPO_ROOT / "evals" / "cases.yaml").read_text())
TEST_AS_OF = date.fromisoformat(SPEC["as_of"])

# ---- one private workspace per browser session; the repo's data folder is never written
if "ws" not in st.session_state:
    st.session_state.ws = Path(tempfile.mkdtemp(prefix="ira_"))
    shutil.copytree(C.DEFAULT_DATA_ROOT, st.session_state.ws / "data")
    (st.session_state.ws / "ledger").mkdir()
    st.session_state.rows = []
WS: Path = st.session_state.ws
LEDGER = WS / "ledger"

STATUS_STYLE = {READY: ("#0F6E56", "#E1F5EE"), REVIEW_FIRST: ("#854F0B", "#FAEEDA"), NEEDS_INFO: ("#A32D2D", "#FCEBEB")}

st.markdown("""<style>
.badge{display:inline-block;padding:3px 10px;border-radius:6px;font-weight:600;font-size:0.85rem;margin-right:8px}
.small{color:#6b6b6b;font-size:0.85rem}
.notrade{padding:8px 12px;border-radius:6px;background:#E1F5EE;color:#085041;font-weight:600}
</style>""", unsafe_allow_html=True)

# ================================================================ sidebar
with st.sidebar:
    st.header("Run settings")
    test_mode = st.checkbox("Test mode", value=True,
                            help="Uses saved EDGAR filing lists and synthetic news only. Never calls live sources. Rows are labelled TEST MODE.")
    scenario = None
    if test_mode:
        labels = ["Data folder as saved"] + [f"{c['id']} · {c['name']}" for c in SPEC["cases"] if c.get("test_mode", True)]
        pick = st.selectbox("Test scenario", labels,
                            help="Each scenario copies the ticker folder and adds or removes files (PRD Q23).")
        if pick != labels[0]:
            scenario = next(c for c in SPEC["cases"] if pick.startswith(c["id"]))
        st.caption(f"Evaluation date fixed at {TEST_AS_OF}.")
    # ---- cost guard: the real model runs only for someone who knows the owner's passcode
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    passcode = os.getenv("APP_PASSCODE", "")
    unlocked = False
    if has_key:
        entered = st.text_input("Owner passcode (enables the real AI model)", type="password",
                                help="Visitors can use the app with the offline mock model and see saved scorecards. "
                                     "Real AI calls are billed to the owner, so they need the passcode.")
        unlocked = bool(passcode) and entered == passcode
        if entered and not unlocked:
            st.error("Wrong passcode. Using the offline mock model.")
    if not unlocked:
        use_mock = True
        st.info("Demo mode: offline mock model (no AI calls, no cost).")
    else:
        use_mock = st.checkbox("Offline mock model (no AI)", value=False,
                               help="Deterministic stand-in for testing the screen without spending credit.")
    cap = int(os.getenv("MAX_MODEL_CALLS_PER_SESSION", "120"))
    st.session_state.setdefault("model_calls", 0)
    if unlocked:
        st.caption(f"Real-model runs this session: {st.session_state.model_calls} of {cap}")
    st.divider()
    st.caption("Research only. No trade, order, brokerage or messaging tool exists in this app.")


class _CountingLLM:
    """Wraps the real model so every call counts toward the per-session cap."""

    def __init__(self, inner):
        self.inner, self.model, self.name = inner, getattr(inner, "model", ""), getattr(inner, "name", "")

    def _tick(self):
        if st.session_state.model_calls >= cap:
            raise LLMError(f"per-session limit of {cap} real-model calls reached")
        st.session_state.model_calls += 1

    def complete_json(self, *a, **k):
        self._tick()
        return self.inner.complete_json(*a, **k)

    def complete_text(self, *a, **k):
        self._tick()
        return self.inner.complete_text(*a, **k)


def llm_or_none():
    try:
        llm = get_llm(use_mock=use_mock)
        return llm if use_mock else _CountingLLM(llm)
    except LLMError as e:
        st.sidebar.error(str(e))
        return None


# ================================================================ helpers
def badge(status: str) -> str:
    fg, bg = STATUS_STYLE.get(status, ("#444", "#eee"))
    return f'<span class="badge" style="color:{fg};background:{bg}">{status}</span>'


def metric_block(col, m, baseline):
    with col:
        if m is None:
            st.metric(label="—", value="withheld")
            return
        if m.value is None:
            st.metric(m.name, m.flag or "withheld")
        else:
            delta = None if baseline is None else f"{(m.value - float(baseline)) * 100:+.1f} pts vs baseline"
            st.metric(m.name, pct(m.value), delta=delta, delta_color="off")
        with st.expander("Supporting information (formula, inputs, citations)"):
            st.code(m.formula, language=None)
            recs = []
            for i in m.inputs:
                val = f"{i.value:,.0f} shares" if i.name == "Share count" and i.value else fmt_money(i.value)
                recs.append({"Input": i.name, "Value": val, "How": i.how,
                             "Source": "\n".join(f"{c.short()} [{c.concept}]" for c in i.citations) or "(computed)"})
            st.dataframe(pd.DataFrame(recs), hide_index=True, width="stretch")
            links = {c.url: f"{c.form} {c.period_end}" for i in m.inputs for c in i.citations if c.url}
            if links:
                st.markdown("Filings on sec.gov: " + " · ".join(f"[{v}]({u})" for u, v in links.items()))
            for a in m.assumptions:
                st.caption("Assumption: " + a)
            for x in m.missing:
                st.error("Missing: " + x)


def rerun_ticker(idx: int, feedback: str):
    old = st.session_state.rows[idx]
    llm = llm_or_none()
    root = old["root"]
    row = run_research(old["row"].ticker, old["row"].price, root, test_mode=old["row"].test_mode,
                       as_of=TEST_AS_OF if old["row"].test_mode else date.today(), feedback=feedback, llm=llm,
                       ledger_root=LEDGER)
    st.session_state.rows[idx] = {"row": row, "root": root, "decision": None, "answer": None, "feedback": feedback}


def ask(row, question: str) -> str:
    llm = llm_or_none()
    if llm is None:
        return "Model not configured."
    ctx = {"status": row.status, "review_first": row.review_first, "missing": row.missing, "brief": row.brief,
           "roe": row.to_record()["roe_supporting_information"],
           "owner_earnings_yield": row.to_record()["owner_earnings_yield_supporting_information"],
           "news": [{k: n[k] for k in ("id", "title", "impact", "causal_path")} for n in row.news],
           "mapping_reasons": row.mapping_reasons}
    return llm.complete_text(ASK_SYSTEM, f"ROW:{json.dumps(ctx, default=str)}\n\nQUESTION: {question}")


# ================================================================ main
st.title("Pre-market Research Agent")
st.caption("Evidence-backed ROE and Owner Earnings Yield for a self-directed investor. "
           "The agent prepares research; Shubhansh makes every decision.")

tab_run, tab_evals, tab_how = st.tabs(["Research", "Evals", "How it works"])

with tab_run:
    c1, c2 = st.columns([2, 3])
    with c1:
        tick_txt = st.text_input("Tickers (1 to 5, comma-separated)", value="CB")
    tickers = [t.strip().upper() for t in tick_txt.split(",") if t.strip()][:5]
    with c2:
        pcols = st.columns(max(1, len(tickers)))
        prices = {}
        for i, t in enumerate(tickers):
            prices[t] = pcols[i].number_input(f"{t} price ($)", min_value=0.0, value=float(SPEC["prices"].get(t, 0.0)),
                                              step=0.01, format="%.2f", key=f"price_{t}")
    if st.button("Run research", type="primary"):
        llm = llm_or_none()
        new_rows = []
        with st.spinner("Checking filings, reading news, computing metrics..."):
            for t in tickers:
                if test_mode and scenario is not None:
                    case = dict(scenario, ticker=t)
                    root, used_t, proxy = build_scenario(case, WS / "data", WS / f"scn_{t}", TEST_AS_OF)
                    if proxy:
                        st.info(f"{t}: real filings not yet in the data folder, so this scenario runs on the fictional EXMP company.")
                    t = used_t
                else:
                    root = WS / "data"
                row = run_research(t, prices.get(t) or prices.get(tickers[0]), root, test_mode=test_mode,
                                   as_of=TEST_AS_OF if test_mode else date.today(), llm=llm, ledger_root=LEDGER)
                new_rows.append({"row": row, "root": root, "decision": None, "answer": None, "feedback": None})
        st.session_state.rows = new_rows

    for idx, item in enumerate(st.session_state.rows):
        row = item["row"]
        st.divider()
        head = badge(row.status) + f"<b>{row.ticker}</b> <span class='small'>as of {row.as_of}" + \
            (" · <b>TEST MODE</b>" if row.test_mode else "") + (f" · model {row.model}" if row.model else "") + "</span>"
        st.markdown(head, unsafe_allow_html=True)
        if item.get("feedback"):
            st.caption(f"Rerun with reviewer guidance: \"{item['feedback']}\"")
        if row.review_first:
            st.warning("**REVIEW FIRST**\n\n" + "\n".join(f"- {r}" for r in row.review_first))
        if row.missing:
            st.error("**Needs information** (metric withheld, nothing estimated)\n\n" + "\n".join(f"- {m}" for m in row.missing))
        if row.what_changed:
            st.markdown("**What changed:** " + " · ".join(row.what_changed))
        if row.roe is not None or row.oey is not None:
            mc1, mc2 = st.columns(2)
            metric_block(mc1, row.roe, row.baseline_roe)
            metric_block(mc2, row.oey, row.baseline_oey)
            if row.ttm_mode:
                st.caption(f"TTM method: {row.ttm_mode}. Filings: " + "; ".join(row.filings_used))
        if row.news:
            st.markdown("**News and events**")
            st.dataframe(pd.DataFrame([{"ID": n["id"], "Impact": n["impact"], "Item": n["title"], "Date": n["date"],
                                        "Why it matters (causal path)": n["causal_path"], "Source": n["url"]} for n in row.news]),
                         hide_index=True, width="stretch")
        if row.brief:
            st.markdown("**Agent brief**")
            st.info(row.brief)
        if row.thesis_check:
            st.markdown(f"**Thesis check:** {row.thesis_check}")
        with st.expander("Checks passed and agent steps"):
            for c in row.checks:
                st.markdown(f"- ✅ {c}")
            if row.mapping_reasons:
                st.markdown("**Line items the model chose for Owner Earnings, and why**")
                st.json(row.mapping_reasons)
            st.markdown("**Agent trace**")
            st.code("\n".join(row.trace) or "(none)", language=None)

        # ---- human checkpoint
        if item["decision"] in ("APPROVED",):
            st.markdown('<div class="notrade">Review recorded. No trade placed.</div>', unsafe_allow_html=True)
            continue
        if item["decision"] == "CANCELLED":
            st.caption("Cancelled. Nothing saved.")
            continue
        note = st.text_area("Reviewer input (max 500 characters)", max_chars=C.MAX_REVIEWER_CHARS, key=f"note_{row.run_id}",
                            placeholder="Your brief on Approve · guidance on Reject (e.g. 'use maintenance capex of $150M') · your question on Ask")
        reviewed = True
        if row.status == REVIEW_FIRST:
            reviewed = st.checkbox("Flagged event reviewed", key=f"flag_{row.run_id}")
        b1, b2, b3, b4 = st.columns(4)
        ldir = LEDGER / row.ticker
        if b1.button("Approve", key=f"ap_{row.run_id}", type="primary",
                     disabled=row.status == NEEDS_INFO or not reviewed,
                     help="Disabled for NEEDS INFORMATION; for REVIEW FIRST, tick 'Flagged event reviewed' first."):
            storage.set_decision(ldir, row.run_id, "APPROVED", note)
            item["decision"] = "APPROVED"
            st.rerun()
        if b2.button("Reject and rerun", key=f"rj_{row.run_id}"):
            if (ldir / C.ANALYSIS_FILE).exists():
                storage.set_decision(ldir, row.run_id, "REJECTED", note)
            rerun_ticker(idx, note)
            st.rerun()
        if b3.button("Ask", key=f"as_{row.run_id}", disabled=not note.strip()):
            item["answer"] = ask(row, note)
            if (ldir / C.ANALYSIS_FILE).exists():
                storage.set_decision(ldir, row.run_id, "ASKED", note, item["answer"])
        if b4.button("Cancel", key=f"cn_{row.run_id}"):
            if (ldir / C.ANALYSIS_FILE).exists():
                storage.set_decision(ldir, row.run_id, "CANCELLED")
            item["decision"] = "CANCELLED"
            st.rerun()
        if item.get("answer"):
            st.markdown(f"**Answer** (brief unchanged): {item['answer']}")

    # ---- the log
    logs = sorted(LEDGER.glob(f"*/{C.ANALYSIS_FILE}"))
    if logs:
        st.divider()
        st.subheader("analysis.xlsx (decision log)")
        for p in logs:
            df = storage.read(p.parent)
            st.caption(f"{p.parent.name}: {len(df)} row(s)")
            st.dataframe(df[["date_time", "ticker", "status", "roe", "owner_earnings_yield", "test_mode",
                             "reviewer_decision", "reviewer_input"]], hide_index=True, width="stretch")
            st.download_button(f"Download {p.parent.name} analysis.xlsx", p.read_bytes(),
                               file_name=f"{p.parent.name}_analysis.xlsx", key=f"dl_{p.parent.name}")

with tab_evals:
    st.subheader("Evaluation scorecard")
    st.caption("15 fixed cases (PRD Q24), each run 3 times. A correct NEEDS INFORMATION or REVIEW FIRST is a pass.")
    ec1, ec2 = st.columns([1, 3], vertical_alignment="bottom")
    n_runs = ec1.selectbox("Runs per case", [1, 3], index=1)
    if ec2.button(f"Run evaluation now ({15 * n_runs} runs, {'mock model' if use_mock else 'real model'})"):
        from evals.run_evals import run_suite  # noqa: PLC0415
        llm = llm_or_none()
        bar, log = st.progress(0.0), st.empty()
        lines: list[str] = []

        def prog(done, total, line):
            lines.append(line)
            bar.progress(done / total)
            log.code("\n".join(lines[-15:]), language=None)

        st.session_state.eval_summary = run_suite(n_runs, llm, WS / "data", scratch=WS / "evals", progress=prog)
    res_dir = C.REPO_ROOT / "evals" / "results"
    files = sorted(res_dir.glob("latest-*.json")) if res_dir.exists() else []
    shown = [("This session", st.session_state.eval_summary)] if st.session_state.get("eval_summary") else []
    shown += [(f.stem, json.loads(f.read_text())) for f in files]
    if not shown:
        st.info("No scorecard yet.")
    for title, data in shown:
        if title == "This session":
            st.download_button("Download this scorecard (JSON)", json.dumps(data, indent=2, default=str),
                               file_name=f"scorecard-{data['when'].replace(' ', '-').replace(':', '')}.json")
        n = data["runs"]
        st.markdown(f"**{title}** · {data['when']} · model `{data['model']}` · Safety **{data['safety_pass']}/{n}** · "
                    f"Fully correct **{data['fully_correct']}/{n}** · Pass mark: {data['pass_mark']}")
        st.dataframe(pd.DataFrame([{"Case": r["case"], "Run": r["run"], "Scenario": r["name"], "Status": r["status"],
                                    "Safety": "PASS" if r["safety_pass"] else "FAIL",
                                    "Correct": "PASS" if r["correct"] else "FAIL",
                                    "Notes": "; ".join(r["notes"])} for r in data["results"]]),
                     hide_index=True, width="stretch")
    fl = C.REPO_ROOT / "evals" / "FAILURES.md"
    if fl.exists():
        st.markdown(fl.read_text())

with tab_how:
    st.markdown((C.REPO_ROOT / "docs" / "HOW_IT_WORKS.md").read_text() if (C.REPO_ROOT / "docs" / "HOW_IT_WORKS.md").exists() else "")
