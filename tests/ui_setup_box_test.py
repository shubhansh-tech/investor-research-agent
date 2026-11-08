"""Browser test of the setup box on the "Setup & filings" tab (10 cases). Runs against the app with a stand-in
for SEC EDGAR (see the session notes); point 1-3 of the owner's spec plus the four refinements and bad input."""
import time
from playwright.sync_api import sync_playwright
URL="http://localhost:8598/"; R=[]
def check(n, ok, extra=""): R.append(ok); print(("PASS " if ok else "FAIL ")+n+("" if ok else f"  ({extra})"))
def box(pg): return pg.get_by_role("textbox", name="Ticker to set up").input_value()
def to_setup(pg):
    pg.get_by_role("tab", name="Setup & filings").click(); pg.get_by_text("QUBT · Set up").wait_for(timeout=60000); time.sleep(0.8)
def research(pg, tickers, prices):
    pg.get_by_role("tab", name="Research").click(); time.sleep(0.5)
    t=pg.get_by_label("Tickers (1 to 5, comma-separated)"); t.click(); t.press("Control+A"); t.type(tickers); pg.keyboard.press("Tab"); time.sleep(1.2)
    for tk, pr in prices: pg.get_by_label(f"{tk} price ($)").fill(pr); pg.keyboard.press("Tab"); time.sleep(1)
    pg.get_by_role("button", name="Run research").click(); pg.get_by_text("Needs information").first.wait_for(timeout=90000) if any(x in tickers.upper() for x in ("TSLA","NVDA")) else time.sleep(8)
    time.sleep(1)
import re
def settle(pg):
    pg.get_by_text("View agent rules").first.wait_for(timeout=60000)
    end=time.time()+20
    while time.time()<end and pg.get_by_text("Checking each ticker").count(): time.sleep(0.2)
    time.sleep(1.0)
def headers(pg):
    settle(pg)
    out=[]
    for h in pg.locator('[data-testid="stMain"] [data-testid="stExpander"] summary').all():
        if h.is_visible():
            out.append(re.sub(r"^keyboard_arrow_\w+", "", h.inner_text().replace("\n", " ")).strip())
    return out
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":1000})
    pg.goto(URL); pg.get_by_text("Pre-market Research Agent").first.wait_for(timeout=30000); time.sleep(1)
    to_setup(pg); check("3a. no Research run -> box empty", box(pg)=="", box(pg))
    research(pg, "tsla, cb, nvda", [("TSLA","400"),("CB","357.37"),("NVDA","180")])
    to_setup(pg); check("1. two tickers need setup -> first one (TSLA)", box(pg)=="TSLA", box(pg))
    pg.screenshot(path="/tmp/claude-0/-home-claude/e11ac70e-1f89-5d11-99b4-e89de80ba238/scratchpad/ui/dbg1.png")
    hs=headers(pg); check("   both listed: TSLA first, NVDA second", hs[0].startswith("🔴 TSLA") and hs[1].startswith("🔴 NVDA"), hs[:3])
    pg.get_by_role("tab", name="Research").click(); time.sleep(0.5)
    pg.get_by_role("button", name="Go to Setup & filings for NVDA").click(); time.sleep(2)
    check("R2. 'Go to Setup' for NVDA wins -> NVDA", box(pg)=="NVDA", box(pg))
    check("   NVDA section first", headers(pg)[0].startswith("🔴 NVDA"), headers(pg)[:2])
    pg.get_by_role("textbox", name="Ticker to set up").fill("cb"); pg.get_by_role("button", name="Set up", exact=True).click(); time.sleep(2)
    check("R3. already set up -> message, CB opened first", pg.get_by_text("CB is already set up").is_visible() and headers(pg)[0].startswith("✅ CB"), headers(pg)[:2])
    pg.get_by_role("textbox", name="Ticker to set up").fill("aapl"); pg.get_by_role("button", name="Set up", exact=True).click(); time.sleep(2)
    hs=headers(pg); check("Set up a typed ticker (AAPL) -> its section first, step 1 red", hs[0].startswith("🔴 AAPL") and "Step 1 of 4" in hs[0], f"{hs} box={box(pg)}")
    pg.get_by_role("textbox", name="Ticker to set up").fill("t$la"); pg.get_by_role("button", name="Set up", exact=True).click(); time.sleep(1.5)
    check("bad input -> clear error", pg.get_by_text("Enter one ticker, for example TSLA.").is_visible())
    research(pg, "cb", [("CB","357.37")])
    to_setup(pg); check("3b. latest run had nothing needing setup -> box empty", box(pg)=="", box(pg))
    research(pg, "cb, tsla", [("CB","357.37"),("TSLA","400")])
    to_setup(pg); check("2. one of several needs setup -> TSLA", box(pg)=="TSLA", box(pg))
    pg.screenshot(path="/tmp/claude-0/-home-claude/e11ac70e-1f89-5d11-99b4-e89de80ba238/scratchpad/ui/setup_box.png", clip={"x":300,"y":180,"width":1100,"height":520})
    b.close()
print(f"\n{sum(R)}/{len(R)} passed")
