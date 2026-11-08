# Design: "Setup & filings" tab

**Status:** v4 (2026-11-08): read-only views of assumptions and rules added, always available, collapsed.
**Scope:** daily use only. Test mode keeps its fixed saved data, so the 45-run evaluation stays repeatable (Q6).
**Storage:** session-only on the hosted app, plus a .zip you download and restore (Q5).

---

## Where it lives (Q1)

A fourth tab: **Research · Setup & filings · Evals · How it works**.

At the top of the tab, a status list of tickers, for example:

| Ticker | Status | Next step |
|---|---|---|
| CB | Ready | - |
| QUBT | New filing needed: 10-Q filed 2026-11-10 | Step 3 |
| TSLA | Setup required | Step 1 |

When a Research run stops with "setup required" or "new filing needed", its message links straight to this tab with that ticker selected (Q4).

## Restore from a previous session (Q5)

First thing on the tab: **[Restore from a saved .zip]**. Upload the .zip you downloaded last time, and every ticker folder comes back. Last thing on the tab: **[Download my setup (.zip)]**. One .zip holds everything (agreed): all ticker folders, your decision logs and your rules.

## Layout: collapsible sections

Every ticker, and every step within a ticker, is a collapsible section. Its header shows its status, so the tab reads like a checklist:

| Header shows | Meaning | Open or closed |
|---|---|---|
| ✅ **Done** · e.g. "Step 2 · Fetch logs: saved 2026-11-08" | Nothing to do | Closed |
| 🔴 **:red[Action required]** · e.g. "Step 3 · Filings: 2 of 3 still needed" | Waiting for you | **Open** |
| 🔒 Locked · e.g. "Step 4 · assumptions.md" | Waits for an earlier step | Closed |

Rules:
- **Only one section is red and open at a time:** the next thing to do. Several red headers at once would lose their meaning.
- The ticker's own header carries the same signal, e.g. "🔴 TSLA · Action required: Step 3 of 4", or "✅ CB · Ready".
- When a step is finished, it closes with a ✅, and the next one opens in red.
- You can still open any section to look, including finished ones.
- **View without editing:** each ticker has a collapsed **"📄 View files"** section showing its `assumptions.md` (as written, plus what the agent understood in plain words), its fetch logs and the list of saved filings. The rules have a collapsed **"📄 View agent rules"** section. Opening these never changes anything: editing is only through the upload buttons, and even then nothing is saved until you confirm.

## The steps for one ticker (Q1, Q2, Q3)

Each step has one button (CTA = call to action) and shows its result before you move on. A step stays locked until the one before it is done.

**Step 1 · Create the folder**
*(Steps: folder → fetch logs → filings → assumptions; agreed.)*
**[Create folder TSLA]** → the app checks the ticker on SEC EDGAR and shows "Tesla, Inc. (SEC CIK 1318605)", so you confirm it's the right company before anything is created.

**Step 2 · Fetch logs**
**[Get fetch logs from EDGAR]** → the app builds both logs (10-K/10-Q and 8-K), including the **8-K item numbers** (for example 2.02 = earnings, 4.02 = restatement), and shows them as tables. Rows that matter for this run are highlighted.
**[Confirm and save logs]** → saved into the folder. Nothing is saved until you confirm. You confirm the whole table at once (agreed); important rows are highlighted.

**Step 3 · Filings**
The app lists the filings needed (latest 10-K, latest 10-Q, the same quarter a year earlier), each with its own link and upload slot. Above the list, these instructions are shown on screen:

> **How to save each filing**
> 1. **Click the filing's link.** It opens the filing itself on sec.gov (the address starts with `https://www.sec.gov/Archives/edgar/data/…` and ends in `.htm`).
> 2. **If you found the filing on EDGAR yourself instead,** the address will look like `https://www.sec.gov/ix?doc=/Archives/edgar/data/…/tsla-20260930.htm`. Click in the address bar, **delete `ix?doc=/`** (so it reads `https://www.sec.gov/Archives/edgar/data/…/tsla-20260930.htm`), and press Enter. The page looks plainer: that's the right one.
> 3. **Save the page:**
>    - **Chrome:** File → *Save Page As…* → Format: **Webpage, HTML Only** → Save.
>    - **Safari:** File → *Save As…* → Format: **Page Source** → Save.
> 4. **Keep the file name the app shows** (for example `tsla-20260930.htm`). Don't add or change the extension.
> 5. **Upload it in the slot next to that filing.** The app checks it at once (below) and tells you if anything is wrong.

The strict check is the safety net for these steps: if a browser saved the wrong thing (for example the viewer page instead of the filing), the upload is rejected with a clear message.
**Strict check on every upload (Q3):** the app reads the cover page and accepts the file only if company, form and period are right. Otherwise it shows an error that names the problem, e.g. "This is QUBT's 10-Q for June 2026; TSLA's 10-Q for September 2026 is needed." A wrong file is never saved.

**Step 4 · assumptions.md (optional)**
**[Upload assumptions.md]** → the app checks the format (the YAML block of standing decisions) and shows what it understood: maintenance capex and each decision in plain words. **[Confirm]** to save. Skipping is fine: the agent then flags one-time items for review.

## Later filings (Q4)

When a company files a new 10-Q or 10-K, the ticker's status changes to "New filing needed" and its section shows:

1. **What's needed, with links:** the new filing, plus the matching quarter a year earlier if it isn't in the folder yet.
2. **Upload slots** with the same strict check.
3. **Fetch log update:** the new EDGAR rows are inserted at the top (EDGAR lists newest first). The app shows the **previous and new version side by side**, with the new rows highlighted. **[Confirm and save]**.
4. The app works out on its own which older 10-Q is no longer needed for the trailing twelve months, and says so.

## Agent rules (all tickers)

`research_rules.md` holds the rules for every ticker, so it sits in its own section at the bottom, not in the per-ticker steps.
**📄 View agent rules** (collapsed, read-only, always there) · **[Upload new rules]** → shows the changes (old vs new, line by line) → **[Confirm]**. Session-only like everything else, and included in the .zip.

---

## Decisions (agreed 2026-11-08)

1. Steps in order: folder → fetch logs → filings → assumptions.md.
2. Rules (`research_rules.md`) in their own section at the bottom, old vs new shown before confirming.
3. One .zip for everything: ticker folders, decision logs and rules.
4. Fetch logs confirmed as a whole table, important rows highlighted.
5. Filings come with step-by-step save instructions on screen (Step 3).

## Technical notes (for the build)

- Streamlit's built-in tabs can't be switched by a link. To make "new filing needed" jump to this tab, I may replace the tab bar with an equivalent one that can be switched in code. It looks the same.
- The 8-K item numbers come from EDGAR's own data service (the same source as the setup panel).
- The fetch log gains an "Items" column. The existing logs for CB and QUBT keep working without it.
