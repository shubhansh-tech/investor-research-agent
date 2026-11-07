# Commit ID map (author fix, 2026-11-07)

From 2026-11-05 08:58 to 2026-11-07, commits were made with the AI assistant's default identity (Claude <noreply@anthropic.com>) instead of the owner's. On 2026-11-07 they were re-stamped with the owner as author; every commit still carries a "Co-Authored-By: Claude" line. Only the author changed: file contents and dates are identical. Commit IDs changed, so older IDs in scorecards, the iteration log and notes map as below. The pre-fix history is kept on branch `backup-before-author-fix-20261107`.

| Old ID | New ID | Date | Commit |
|---|---|---|---|
| `adaea40` | `8e9f1c2` | 2026-11-05 08:58 | Brief written after the calculator, with code checks on every number and decision |
| `ea65b4d` | `20d7fc9` | 2026-11-05 08:58 | Escape $ on screen; brief shown as headline plus Fact/Inference sections |
| `130c824` | `a9be9ae` | 2026-11-05 08:58 | Iteration log: brief problems #19-21 |
| `d24a54d` | `9ef1f57` | 2026-11-05 09:28 | Daily use: live news search on approved sites, links checked by code (PRD search_news) |
| `fe38b7f` | `2ef0ab4` | 2026-11-05 09:28 | E-15 grader reports the news search |
| `1b37bbe` | `c8a73d0` | 2026-11-05 09:28 | Docs and iteration log #22: live news search |
| `5096be2` | `7680e1b` | 2026-11-05 09:41 | Brief: at most 200 words plus News that matters (at most 5 items, 200 words) counted separately |
| `40b8877` | `8a00783` | 2026-11-05 09:41 | Rules and docs: separate brief and news word limits |
| `7e06efa` | `b98ea62` | 2026-11-05 09:49 | Version label: look up the commit on every call, so it updates after a push without a reboot |
| `7fe072b` | `e6e0150` | 2026-11-05 10:01 | News search: skip approved sites that block Anthropic's crawler; retry once naming them on screen |
| `42598d5` | `fc7d6de` | 2026-11-05 10:27 | Use New York time for every date and time (server runs on UTC) |
| `a64ab44` | `df38fea` | 2026-11-05 10:38 | Brief: describe removed standing decisions in plain words (no 'removes -$17.7M') |
| `31065db` | `8956859` | 2026-11-05 13:50 | Scorecard a64ab44 (batch 2b-brief): 45/45 safety, 42/45 correct |
| `725e9bc` | `896014b` | 2026-11-05 13:50 | Brief: structured output, share price allowed, removed decisions only in plain words |
| `66c17f8` | `92940c3` | 2026-11-05 13:50 | Iteration log #25 |
| `417d6df` | `cdf5477` | 2026-11-05 13:50 | Scorecard table: a64ab44 is 42/45 |
| `a4aa0d1` | `296f165` | 2026-11-06 17:23 | Decision log: show only the tickers on screen; other session tickers in a closed section |
| `4cbf58e` | `6a5fb12` | 2026-11-06 18:26 | Daily use by default; empty ticker and price fields outside test mode, price hint today's / target |
| `12ab7d3` | `f8a7ddb` | 2026-11-06 18:46 | Upload a saved decision log; Clear my session data; delete session folders unused for 12 hours |
| `2ead211` | `630847b` | 2026-11-06 18:46 | Iteration log #27 |
| `aa28288` | `9c7545d` | 2026-11-06 22:32 | Brief: structured outputs (output_config.format) instead of forced tool_choice; fall back to plain JSON if refused |
| `ccf9ac9` | `b78d7f4` | 2026-11-06 22:32 | Iteration log #28 |
| `ec4723a` | `4b4583b` | 2026-11-07 10:39 | Keyboard flow: Tab/Enter moves tickers -> prices -> Run research; text price boxes with validation; browser tests |
| `32a3b41` | `3fe73e2` | 2026-11-07 10:39 | Iteration log #29 |
| `fea7c67` | `480fc4d` | 2026-11-07 10:40 | Browser test file: keyboard flow (14 cases) |
