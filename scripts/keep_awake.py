"""Keep the hosted demo awake: open it in a headless browser, click Streamlit's wake-up button if the
app is asleep, and wait until the app itself has loaded. Run by .github/workflows/keep-awake.yml.
No passwords, no AI calls: it only opens the public page like a visitor would."""
import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://investor-research-agent.streamlit.app/")
TITLE = "Pre-market Research Agent"
WAKE = "Yes, get this app back up"


def app_loaded(page) -> bool:
    # On Streamlit Community Cloud the app runs inside a frame of the page, so look in every frame.
    for frame in page.frames:
        try:
            if frame.get_by_text(TITLE).count():
                return True
        except Exception:  # noqa: BLE001  (a frame can disappear while loading)
            pass
    return False


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        woke = False
        deadline = time.time() + 300
        while time.time() < deadline:
            if app_loaded(page):
                print(f"OK: app is up{' (it was asleep and was woken)' if woke else ''}.")
                time.sleep(20)          # stay briefly, like a real visit
                browser.close()
                return 0
            button = page.get_by_role("button", name=WAKE)
            if not woke and button.count():
                print("App was asleep: clicking the wake-up button.")
                button.first.click()
                woke = True
            time.sleep(5)
        page.screenshot(path="keep_awake_failure.png", full_page=True)
        browser.close()
        print("FAILED: the app did not load within 5 minutes (screenshot saved).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
