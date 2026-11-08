"""Browser rehearsal of a first-time setup (QUBT from scratch) through all 4 steps, including wrong uploads.
Start the app with the EDGAR stand-in first:  streamlit run tests/fixtures/wrap_app.py --server.port 8597"""
import os
FIX = os.path.join(os.path.dirname(__file__), "fixtures")
import time, re
from playwright.sync_api import sync_playwright
S=os.environ.get("TEST_OUT", "/tmp")
D="/home/claude/investor-research-agent/data"
R=[]
def check(n, ok, extra=""): R.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  ({extra})"))
def settle(pg):
    time.sleep(0.8); end=time.time()+40
    while time.time()<end and (pg.get_by_text("Checking each ticker").count() or pg.locator('[data-testid="stStatusWidget"]').count()): time.sleep(0.3)
    time.sleep(0.8)
def header(pg):
    for h in pg.locator('[data-testid="stMain"] [data-testid="stExpander"] summary').all():
        if h.is_visible(): return re.sub(r"^keyboard_arrow_\w+", "", h.inner_text().replace("\n"," ")).strip()
def slot_input(pg, slot):
    return pg.locator(f'[aria-label="{slot}"] input[type="file"]')
def upload(pg, slot, path):
    slot_input(pg, slot).set_input_files(path); settle(pg)
def clear(pg, slot):
    btn = pg.locator('[data-testid="stFileUploaderDeleteBtn"] button')
    if btn.count(): btn.first.click(); settle(pg)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":1100})
    pg.goto("http://localhost:8597/"); pg.get_by_text("Pre-market Research Agent").first.wait_for(timeout=30000); time.sleep(1)
    pg.get_by_role("tab", name="Setup & filings").click(); settle(pg)
    pg.get_by_role("textbox", name="Ticker to set up").fill("qubt"); pg.get_by_role("button", name="Set up", exact=True).click(); settle(pg)
    check("Set up QUBT -> step 1 red", "QUBT" in header(pg) and "Step 1 of 4" in header(pg), header(pg))
    pg.get_by_role("button", name="Look up QUBT on SEC EDGAR").click(); settle(pg)
    check("Step 1: company shown before creating", pg.get_by_text("Quantum Computing Inc.").first.is_visible())
    pg.get_by_role("button", name="Create folder QUBT").click(); settle(pg)
    check("Step 1 done -> step 2 red", "Step 2 of 4" in header(pg), header(pg))
    pg.get_by_role("button", name="Get fetch logs from EDGAR").click(); settle(pg)
    check("Step 2: both logs shown with 8-K items", pg.get_by_text("highlighted rows carry item 2.02").is_visible())
    pg.screenshot(path=S+"/ui/step2.png", clip={"x":300,"y":150,"width":1100,"height":950})
    pg.get_by_role("button", name="Confirm and save both logs").click(); settle(pg)
    check("Step 2 done -> step 3 red", "Step 3 of 4" in header(pg), header(pg))
    check("Step 3: save instructions shown", pg.get_by_text("How to save each filing").is_visible())
    upload(pg, "Upload qubt-20251231.htm", f"{D}/CB/filings/cb-20251231.htm")
    check("wrong company rejected", pg.get_by_text(re.compile(r"This is CHUBB.*QUBT's 10-K for the period ended 2025-12-31 is needed", re.I)).first.is_visible())
    clear(pg, "Upload qubt-20251231.htm")
    upload(pg, "Upload qubt-20251231.htm", f"{D}/QUBT/filings/qubt-20260630.htm")
    check("right company, wrong period rejected", pg.get_by_text(re.compile(r"This is QUBT's 10-Q for the period ended 2026-06-30; the 10-K for the period ended 2025-12-31 is needed")).first.is_visible())
    clear(pg, "Upload qubt-20251231.htm")
    upload(pg, "Upload qubt-20251231.htm", f"{FIX}/viewer_page.htm")
    check("viewer page rejected with ix?doc hint", pg.get_by_text(re.compile("probably the EDGAR viewer page")).first.is_visible())
    clear(pg, "Upload qubt-20251231.htm")
    for name in ("qubt-20251231.htm", "qubt-20260630.htm", "qubt-20250630.htm"):
        upload(pg, f"Upload {name}", f"{D}/QUBT/filings/{name}")
        if name == "qubt-20251231.htm":
            check("after 1 of 3: step 3 still red, '1 of 3 saved'", "Step 3 of 4" in header(pg) and pg.get_by_text(re.compile("1 of 3 saved")).first.is_visible(), header(pg))
    h=header(pg); check("Step 3 done after 3 correct uploads -> set up", h.startswith("✅ QUBT"), h)
    upload(pg, "Upload assumptions.md", f"{FIX}/bad_assumptions.md")
    check("bad assumptions.md -> problem shown, no confirm", pg.locator('[data-testid="stAlert"]').filter(has_text="maybe").count()>0 or pg.get_by_text(re.compile("treatment", re.I)).count()>0, "")
    clear(pg, "Upload assumptions.md")
    upload(pg, "Upload assumptions.md", f"{D}/QUBT/assumptions.md")
    check("good assumptions.md -> understood in plain words", pg.get_by_text(re.compile("taken out of owner earnings")).first.is_visible())
    pg.get_by_role("button", name="Confirm and save assumptions.md").click(); settle(pg)
    check("Step 4 done", pg.get_by_text(re.compile(r"Step 4 · assumptions.md: Saved")).first.is_visible())
    pg.screenshot(path=S+"/ui/steps_done.png", clip={"x":300,"y":150,"width":1100,"height":600})
    b.close()
print(f"\n{sum(R)}/{len(R)} passed")
