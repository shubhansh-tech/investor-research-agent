# Commit ID map (author fix, 2026-11-07)

On 2026-11-07 every commit was re-stamped so the author is the owner's GitHub account email
(Shubhansh Karnick <karnick.sh@gmail.com>, account shubhansh-tech). Before that, commits had used
another personal email (Oct 29 to Nov 5) or, by mistake, the AI assistant's default identity
(Nov 5 08:58 to Nov 7). Every commit made with the assistant still carries a "Co-Authored-By: Claude" line.

Only the author changed: file contents and dates are identical. Commit IDs changed, so the IDs quoted in
scorecards, the iteration log and notes before this date map as below. The earlier histories are kept on
branches `backup-before-author-fix-20261107` (original) and `backup-before-email-fix-20261107`; the
capstone fallback branch `v0.0-base-20261101` was not changed.

| Original ID | New ID | Date | Commit |
|---|---|---|---|
| `bf2f42a` | `e34b7f1` | 2026-10-29 15:29 | Start: iXBRL filing parser, filing checks, EXMP test fixture |
| `6caa423` | `da9d5b1` | 2026-10-29 15:33 | Add calculator, validator, news detectors, model step and orchestrator |
| `d99eeeb` | `e256244` | 2026-10-29 15:38 | Add review screen, 15-case eval harness, in-app eval runner, docs and deploy config |
| `96b819d` | `8ff4260` | 2026-10-29 16:12 | Fix statement-section detection and operating cash-flow candidates found on real QUBT 10-K; add QUBT FY2025 10-K |
| `88b81bc` | `f1ac70c` | 2026-10-29 16:28 | Add QUBT Q2 2025 and Q2 2026 10-Qs; show one decimal for amounts under $100M |
| `eebb019` | `a6ebe01` | 2026-10-29 16:31 | Add CB filings; accept cover-page dates split by formatting; guard missing 10-K |
| `fcbc67e` | `7ea76d4` | 2026-10-29 16:33 | Match cash-flow lines by printed label when tags differ across filings; add per-ticker assumptions.md (owned by investor) |
| `546630f` | `f78b8a1` | 2026-10-29 22:07 | Add CB fetch logs and EDGAR test snapshot (as of 2026-10-23); read EDGAR exports with title rows; Oct 23 prices; clearer missing-input messages |
| `70abb8c` | `5cba687` | 2026-10-29 22:19 | Add QUBT fetch logs and test snapshot; treat cash-flow lines not presented in a statement as $0 (disclosed); iteration log |
| `48b5ed2` | `d32f2db` | 2026-10-30 14:07 | Cost guard: real AI calls require owner passcode; per-session call cap; visitors get the offline mock |
| `2e5161c` | `d96426e` | 2026-10-31 15:23 | CB maintenance-capex assumption ($637M, Shubhansh); add back the same estimate when depreciation is undisclosed; grader accepts owner assumptions |
| `5b21d6c` | `8930df5` | 2026-11-01 09:25 | Add eval-run checklist |
| `ab9b2e0` | `715a8a8` | 2026-11-01 10:31 | E-15: count as correct only when live EDGAR is reached; more test/live separation checks |
| `b852a6e` | `a38a9e5` | 2026-11-01 11:15 | Evals tab: bottom-align the run button with the runs-per-case dropdown |
| `8542ae1` | `9c99c21` | 2026-11-01 11:57 | Evals: checkpoint after every run, Resume button, parse each filing once (faster, less memory) |
| `1227ffe` | `67f3282` | 2026-11-04 16:33 | E-11: quoting a detected injection no longer blocks the row |
| `edb34ca` | `7076332` | 2026-11-04 16:33 | Repair small JSON slips in model output before retrying |
| `27979ec` | `0731cfe` | 2026-11-04 16:33 | Owner earnings: read add-backs from the cash-flow statement (sign fix); use current 10-Q comparison column for missing prior-year lines |
| `e07bdde` | `c29ce1a` | 2026-11-04 16:33 | Add CB FY2023 10-K (history, not yet used) and iteration log entries 12-15 |
| `ccbd6c7` | `21db1e9` | 2026-11-04 16:39 | Show the running code version (commit ID) in the sidebar and record it in every scorecard |
| `686f0fd` | `4941dd0` | 2026-11-04 17:47 | Save real-model scorecards: Nov 1 baseline (8542ae1) and Nov 4 batch 1 (ccbd6c7) |
| `c653dd7` | `3c240da` | 2026-11-04 18:23 | Record owner-earnings policy decisions for CB #1-#4 and the per-ticker review workflow (not read by the agent) |
| `aae3863` | `651c352` | 2026-11-05 00:31 | Policy decisions: CB Other line and float, 8-K handling, QUBT warrants, averaging windows, alarm base (record only; not read by the agent) |
| `08f23df` | `9661fa2` | 2026-11-05 07:52 | Standing decisions for CB (12 items incl. float) and QUBT (warrants) in assumptions.md |
| `0f4c0fc` | `4ca8144` | 2026-11-05 07:52 | Apply standing decisions: override model line-item choices, 5-year history from history/ 10-Ks, both numbers shown, size/deviation alarms; drop news/filing ids and decided items from one-time items; fix depreciation add-back when only amortization is disclosed |
| `3ec7099` | `35e7949` | 2026-11-05 07:52 | E-05 expectation REVIEW FIRST (deviation alarm on CB Other line), updated before the batch 2a run; iteration log 16-18 |
| `0d70f87` | `92236ab` | 2026-11-05 08:08 | Save batch 2a scorecard (3ec7099): 45/45 safety, 44/45 fully correct, pass mark met |
| `adaea40` | `377149a` | 2026-11-05 08:58 | Brief written after the calculator, with code checks on every number and decision |
| `ea65b4d` | `6edd80c` | 2026-11-05 08:58 | Escape $ on screen; brief shown as headline plus Fact/Inference sections |
| `130c824` | `43db22d` | 2026-11-05 08:58 | Iteration log: brief problems #19-21 |
| `d24a54d` | `75b656e` | 2026-11-05 09:28 | Daily use: live news search on approved sites, links checked by code (PRD search_news) |
| `fe38b7f` | `fa5cb67` | 2026-11-05 09:28 | E-15 grader reports the news search |
| `1b37bbe` | `4da043c` | 2026-11-05 09:28 | Docs and iteration log #22: live news search |
| `5096be2` | `3539954` | 2026-11-05 09:41 | Brief: at most 200 words plus News that matters (at most 5 items, 200 words) counted separately |
| `40b8877` | `ff55e8e` | 2026-11-05 09:41 | Rules and docs: separate brief and news word limits |
| `7e06efa` | `8948a02` | 2026-11-05 09:49 | Version label: look up the commit on every call, so it updates after a push without a reboot |
| `7fe072b` | `91a211a` | 2026-11-05 10:01 | News search: skip approved sites that block Anthropic's crawler; retry once naming them on screen |
| `42598d5` | `46f761e` | 2026-11-05 10:27 | Use New York time for every date and time (server runs on UTC) |
| `a64ab44` | `04b0bc9` | 2026-11-05 10:38 | Brief: describe removed standing decisions in plain words (no 'removes -$17.7M') |
| `31065db` | `665be31` | 2026-11-05 13:50 | Scorecard a64ab44 (batch 2b-brief): 45/45 safety, 42/45 correct |
| `725e9bc` | `491bc1e` | 2026-11-05 13:50 | Brief: structured output, share price allowed, removed decisions only in plain words |
| `66c17f8` | `e5046dd` | 2026-11-05 13:50 | Iteration log #25 |
| `417d6df` | `1632174` | 2026-11-05 13:50 | Scorecard table: a64ab44 is 42/45 |
| `a4aa0d1` | `f652e17` | 2026-11-06 17:23 | Decision log: show only the tickers on screen; other session tickers in a closed section |
| `4cbf58e` | `50a3aac` | 2026-11-06 18:26 | Daily use by default; empty ticker and price fields outside test mode, price hint today's / target |
| `12ab7d3` | `c96bf8b` | 2026-11-06 18:46 | Upload a saved decision log; Clear my session data; delete session folders unused for 12 hours |
| `2ead211` | `58bab56` | 2026-11-06 18:46 | Iteration log #27 |
| `aa28288` | `93e93ad` | 2026-11-06 22:32 | Brief: structured outputs (output_config.format) instead of forced tool_choice; fall back to plain JSON if refused |
| `ccf9ac9` | `65d8574` | 2026-11-06 22:32 | Iteration log #28 |
| `ec4723a` | `2fa676d` | 2026-11-07 10:39 | Keyboard flow: Tab/Enter moves tickers -> prices -> Run research; text price boxes with validation; browser tests |
| `32a3b41` | `35730c4` | 2026-11-07 10:39 | Iteration log #29 |
| `fea7c67` | `a94b240` | 2026-11-07 10:40 | Browser test file: keyboard flow (14 cases) |
