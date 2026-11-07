"""Browser test of the keyboard flow on the Research tab (Playwright + Chromium).

Tab or Enter moves Tickers -> each price box -> Run research; an invalid price keeps the cursor;
mouse clicks and Shift+Tab are respected; fast typing never overwrites a box.
Run against a local app:  APP_URL=http://localhost:8599/ python tests/ui_focus_test.py
"""
import time
from playwright.sync_api import sync_playwright
import os
URL = os.getenv("APP_URL", "http://localhost:8599/")  # start the app first: streamlit run app.py --server.port 8599
results = []
def focused(page):
    return page.evaluate("""() => { const e = document.activeElement; if (!e) return null;
        return e.tagName === 'INPUT' ? 'input:' + e.getAttribute('aria-label') : (e.tagName === 'BUTTON' ? 'button:' + e.innerText.trim() : e.tagName); }""")
def wait_focus(page, want, timeout=6):
    end = time.time() + timeout
    while time.time() < end:
        if focused(page) == want: return True
        time.sleep(0.1)
    return False
def check(name, ok, page=None):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  (focus is {focused(page)})"))
def fresh(p):
    b = p.chromium.launch(); page = b.new_page(viewport={"width": 1400, "height": 900})
    page.goto(URL); page.get_by_label("Tickers (1 to 5, comma-separated)").wait_for(timeout=30000); time.sleep(1.5)
    return b, page
def tickers(page): return page.get_by_label("Tickers (1 to 5, comma-separated)")
def price(page, t): return page.get_by_label(f"{t} price ($)")
with sync_playwright() as p:
    # A-C: two tickers, Tab through to Run research
    b, page = fresh(p)
    tickers(page).click(); tickers(page).type("cb, qubt"); page.keyboard.press("Tab")
    check("A. tickers + Tab -> first price box", wait_focus(page, "input:CB price ($)"), page)
    page.keyboard.type("357.37"); page.keyboard.press("Tab")
    check("B. price 1 + Tab -> next price box", wait_focus(page, "input:QUBT price ($)"), page)
    page.keyboard.type("6.52"); page.keyboard.press("Tab")
    check("C. last price + Tab -> Run research", wait_focus(page, "button:Run research"), page)
    # D: invalid price stays, error shown, button disabled
    price(page, "CB").click(); page.keyboard.press("Control+A"); page.keyboard.type("abc"); page.keyboard.press("Tab")
    ok = wait_focus(page, "input:CB price ($)") and page.get_by_text("Not a number.").is_visible() and page.get_by_role("button", name="Run research").is_disabled()
    check("D. invalid price -> cursor stays, error shown, Run disabled", ok, page)
    # E: change a price then click elsewhere with the mouse -> no focus steal
    page.keyboard.press("Control+A"); page.keyboard.type("350"); 
    tickers(page).click(); time.sleep(2.5)
    check("E. mouse click elsewhere is respected", focused(page) == "input:Tickers (1 to 5, comma-separated)", page)
    # F: change a price then Shift+Tab -> no forward jump
    price(page, "QUBT").click(); page.keyboard.press("Control+A"); page.keyboard.type("6.60"); page.keyboard.press("Shift+Tab"); time.sleep(2.5)
    check("F. Shift+Tab goes back, not forward", focused(page) != "button:Run research", page)
    # H: Tab without changing a value moves natively to the next box (no -/+ buttons in between)
    price(page, "CB").click(); page.keyboard.press("Tab")
    check("H. Tab with no change -> next price box", wait_focus(page, "input:QUBT price ($)"), page)
    b.close()
    # G + J: single ticker; Enter instead of Tab
    b, page = fresh(p)
    tickers(page).click(); tickers(page).type("cb"); page.keyboard.press("Enter")
    check("G. one ticker + Enter -> its price box", wait_focus(page, "input:CB price ($)"), page)
    page.keyboard.type("$357.37"); page.keyboard.press("Enter")
    check("J. price with $ + Enter -> Run research", wait_focus(page, "button:Run research"), page)
    # K: add a ticker later -> cursor goes to the new, empty box
    tickers(page).click(); page.keyboard.press("End"); page.keyboard.type(", qubt"); page.keyboard.press("Tab")
    check("K. ticker added later -> the new empty price box", wait_focus(page, "input:QUBT price ($)"), page)
    b.close()
    # I: skip the first box, fill the last -> back to the missing one
    b, page = fresh(p)
    tickers(page).click(); tickers(page).type("cb, qubt"); page.keyboard.press("Tab")
    wait_focus(page, "input:CB price ($)"); page.keyboard.press("Tab")
    wait_focus(page, "input:QUBT price ($)"); page.keyboard.type("6.52"); page.keyboard.press("Tab")
    check("I. last price filled but first empty -> back to the empty box", wait_focus(page, "input:CB price ($)"), page)
    # M: duplicates and more than 5
    tickers(page).click(); page.keyboard.press("Control+A"); page.keyboard.type("cb, cb, a, b, c, d, e"); page.keyboard.press("Tab"); time.sleep(2)
    n = page.locator('input[aria-label$="price ($)"]').count()
    check("M. duplicates removed, only 5 used, note shown", n == 5 and page.get_by_text("Only the first 5 tickers are used (E left out).").is_visible(), page)
    b.close()
    # L: test mode -> prefilled, and switching mode does not grab the cursor
    b, page = fresh(p)
    page.get_by_text("Test mode", exact=True).click(); time.sleep(2.5)
    ok = price(page, "CB").input_value() == "357.37" and not (focused(page) or "").startswith("input:CB")
    check("L. test mode prefilled CB 357.37, no cursor jump on mode switch", ok, page)
    b.close()
# N: very fast typist (no pause at all between boxes)
with sync_playwright() as p:
    b, page = fresh(p)
    tickers(page).click(); tickers(page).type("cb, qubt"); page.keyboard.press("Tab"); wait_focus(page, "input:CB price ($)")
    page.keyboard.type("357.37"); page.keyboard.press("Tab"); page.keyboard.type("6.52"); page.keyboard.press("Tab")
    time.sleep(3)
    ok = focused(page) == "button:Run research" and price(page, "QUBT").input_value() == "6.52"
    check("N. fast typing: ends on Run research, nothing overwritten", ok, page)
    b.close()
print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
