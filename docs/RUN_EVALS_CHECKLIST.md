# Running the 45-run evaluation: checklist

App: https://investor-research-agent.streamlit.app

1. **Before clicking:** passcode entered in the sidebar, **Offline mock model unticked**, and the
   button reads **"Run evaluation now (45 runs, real model)"**. If it says "mock model", the AI
   is not on.
2. **Keep the Mac awake and the tab open.** The run takes roughly 15–25 minutes. If the Mac
   sleeps or the tab closes, the run stops. To be safe, run `caffeinate -d` in Terminal; it keeps
   the screen awake until you press Control-C.
3. **Watch the first 2–3 lines** of the progress log. If they show errors (e.g. "model call
   failed"), stop and send a screenshot rather than burning through all 45.
4. **When it finishes,** click **Download this scorecard (JSON)** and upload it to the chat.

**If it stops part-way:** results are saved on the server after every run. Reload the page,
enter the passcode, open the Evals tab, keep Runs per case = 3, and click **Resume (N of 45 done)**.
The partial scorecard is also downloadable at any time. (An app restart, e.g. after a code push,
does wipe the server checkpoint, so no pushes during a run.)

**Cost check:** at most 2 model calls per run (one retry allowed), so 45 runs use at most 90 of
the 120-call session cap.
