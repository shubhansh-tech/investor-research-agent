"""Browser test of the "new filing needed" flow (8 cases): QUBT is set up, then EDGAR lists its Q3 10-Q.
The two September 10-Qs are test copies of QUBT's June 10-Qs with the period changed, made below.
Start the app first:  streamlit run tests/fixtures/wrap_app_after_q3.py --server.port 8596"""
import os, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = tempfile.mkdtemp()
for src_name, dst_name in (("qubt-20260630.htm", "qubt-20260930.htm"), ("qubt-20250630.htm", "qubt-20250930.htm")):
    t = open(f"{REPO}/data/QUBT/filings/{src_name}", encoding="utf-8", errors="surrogateescape").read()
    i = t.find('name="dei:DocumentPeriodEndDate"'); j = t.find("June 30", i)
    t = t[:j] + "September 30" + t[j + len("June 30"):]
    open(f"{OUT}/{dst_name}", "w", encoding="utf-8", errors="surrogateescape").write(t)
import time, re
from playwright.sync_api import sync_playwright
S=OUT
R=[]
def check(n, ok, extra=""): R.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  ({extra})"))
def settle(pg):
    time.sleep(0.8); end=time.time()+60
    while time.time()<end and (pg.get_by_text("Checking each ticker").count() or pg.locator('[data-testid="stStatusWidget"]').count()): time.sleep(0.3)
    time.sleep(0.8)
def headers(pg):
    out=[]
    for h in pg.locator('[data-testid="stMain"] [data-testid="stExpander"] summary').all():
        if h.is_visible(): out.append(re.sub(r"^keyboard_arrow_\w+", "", h.inner_text().replace("\n"," ")).strip())
    return out
def qubt(pg): return next((h for h in headers(pg) if "QUBT" in h and "View files" not in h), "")
def upload(pg, slot, path): pg.locator(f'[aria-label="{slot}"] input[type="file"]').set_input_files(path); settle(pg)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":1200})
    pg.goto("http://localhost:8596/"); pg.get_by_text("Pre-market Research Agent").first.wait_for(timeout=30000); time.sleep(1)
    pg.get_by_role("tab", name="Setup & filings").click(); settle(pg)
    check("QUBT starts as set up (green)", qubt(pg).startswith("✅ QUBT"), qubt(pg))
    pg.get_by_text(re.compile(r"QUBT · Set up")).first.click(); settle(pg)
    pg.get_by_role("button", name="Check EDGAR for new filings").nth(1).click() if pg.get_by_role("button", name="Check EDGAR for new filings").count()>1 else pg.get_by_role("button", name="Check EDGAR for new filings").first.click()
    settle(pg)
    h=qubt(pg); check("after the check: red, new filing needed (10-Q filed 2026-11-09)", h.startswith("🔴 QUBT") and "10-Q filed 2026-11-09" in h, h)
    check("both 10-Qs listed as missing (this year and a year earlier)", pg.get_by_text("qubt-20260930.htm").first.is_visible() and pg.get_by_text("qubt-20250930.htm").first.is_visible())
    check("logs: current beside updated, confirm held back until filings saved", pg.get_by_text(re.compile(r"Updated 10-K-10-Q_fetch_log.xlsx \(1 new row")).first.is_visible() and pg.get_by_text(re.compile("Save the filing\\(s\\) above first")).first.is_visible() and pg.get_by_role("button", name="Confirm and save the updated logs").count()==0)
    pg.screenshot(path=S+"/update_flow.png", full_page=True)
    upload(pg, "Upload qubt-20260930.htm", f"{REPO}/data/QUBT/filings/qubt-20260630.htm")
    check("wrong period rejected", pg.get_by_text(re.compile(r"This is QUBT's 10-Q for the period ended 2026-06-30")).first.is_visible())
    upload(pg, "Upload qubt-20260930.htm", S+"/qubt-20260930.htm")
    upload(pg, "Upload qubt-20250930.htm", S+"/qubt-20250930.htm")
    check("both saved -> 'all saved', confirm button appears", pg.get_by_text(re.compile("all saved")).first.is_visible() and pg.get_by_role("button", name="Confirm and save the updated logs").count()==1)
    check("old 10-Qs reported as no longer used", pg.get_by_text(re.compile(r"No longer used .*qubt-20250630\.htm.*qubt-20260630\.htm")).first.is_visible())
    pg.get_by_role("button", name="Confirm and save the updated logs").click(); settle(pg)
    h=qubt(pg); check("after confirming: green again, up to date", h.startswith("✅ QUBT · Up to date with SEC EDGAR"), h)
    b.close()
print(f"\n{sum(R)}/{len(R)} passed")
