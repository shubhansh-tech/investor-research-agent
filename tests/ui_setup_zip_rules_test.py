"""Browser test of rules upload (changes shown, confirm), Download my setup (.zip), Clear my session data,
and Restore from the .zip (7 cases). Start the app first:  streamlit run app.py --server.port 8599"""
import time, re, os
from playwright.sync_api import sync_playwright
import tempfile
S=tempfile.mkdtemp()
FIX=os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
R=[]
def check(n, ok, extra=""): R.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  ({extra})"))
def settle(pg):
    time.sleep(0.8); end=time.time()+60
    while time.time()<end and (pg.get_by_text("Checking each ticker").count() or pg.locator('[data-testid="stStatusWidget"]').count()): time.sleep(0.3)
    time.sleep(0.8)
def to_setup(pg): pg.get_by_role("tab", name="Setup & filings").click(); settle(pg)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":1200}, accept_downloads=True)
    pg.goto("http://localhost:8599/"); pg.get_by_text("Pre-market Research Agent").first.wait_for(timeout=30000); time.sleep(1)
    to_setup(pg)
    # rules: upload, see the changes, confirm
    pg.get_by_text("View agent rules").click(); settle(pg)
    pg.locator('[aria-label="Upload new research_rules.md"] input[type="file"]').set_input_files(FIX+"/new_rules_test.md"); settle(pg)
    check("rules: changes shown before confirming", pg.get_by_text("This line was added in the test.").first.is_visible() and pg.get_by_role("button", name="Confirm new rules").is_visible())
    pg.get_by_role("button", name="Confirm new rules").click(); settle(pg)
    if not pg.get_by_text("New rules saved for this session").count(): pg.get_by_text("View agent rules").click(); settle(pg)
    check("rules: saved for the session", pg.get_by_text("New rules saved for this session").first.is_visible())
    # download
    pg.get_by_role("button", name="Prepare my setup for download").click(); settle(pg)
    with pg.expect_download() as dl:
        pg.get_by_role("button", name=re.compile(r"Download my setup \(\.zip")).click()
    path=S+"/setup.zip"; dl.value.save_as(path)
    check("download: a .zip of a sensible size", os.path.getsize(path) > 500_000, os.path.getsize(path))
    # clear the session -> rules back to original
    pg.get_by_role("button", name="Clear my session data").click(); settle(pg); to_setup(pg)
    pg.get_by_text("View agent rules").click(); settle(pg)
    loc=pg.get_by_text("This line was added in the test.")
    check("after clearing: original rules again", not any(loc.nth(i).is_visible() for i in range(loc.count())))
    # restore
    pg.get_by_text("Restore my setup from a saved .zip").click(); settle(pg)
    pg.locator('[aria-label="Saved setup (.zip)"] input[type="file"]').set_input_files(path); settle(pg)
    check("restore: preview lists what will come back", pg.get_by_text(re.compile(r"This will restore")).first.is_visible() and pg.get_by_text("Agent rules (research_rules.md)").first.is_visible())
    pg.get_by_role("button", name="Confirm restore").click(); settle(pg)
    check("restore: success message", pg.get_by_text(re.compile(r"^Restored ")).first.is_visible())
    def rules_visible():
        loc=pg.get_by_text("This line was added in the test."); return any(loc.nth(i).is_visible() for i in range(loc.count()))
    if not rules_visible():
        pg.get_by_text("View agent rules").click(); settle(pg)
    check("restore: the edited rules are back", rules_visible())
    pg.screenshot(path=S+"/restore.png", clip={"x":300,"y":150,"width":1100,"height":700})
    b.close()
print(f"\n{sum(R)}/{len(R)} passed")
