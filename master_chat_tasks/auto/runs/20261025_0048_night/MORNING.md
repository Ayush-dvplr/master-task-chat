# MORNING report (night mode 2026-10-25T00:48:20+05:30 -> 2026-10-25T08:30+05:30)

Written by the master chat during the night. Ayush reads this first.

## In short
- Seven probes ran tonight: sentinel, sensor, district, tariff, caldermoor, metered and config. Every one got tests 98.45-100. No task met the gate (tests < 100, rubric < 100, overall < 70).
- Every trap shape we tried was read correctly by fresh Opus. That covers explicit H7 re-share, H6 chains and counters, H3 defined terms, and the glossary-only recursive term. Six tasks are parked. Tariff r2 waits for your go.
- About 3 hours were lost from 02:33 to 05:40 to the usage limit. A harness login fault then blocked the 05:50 and 05:57 resumes; I fixed it at 06:00.

## Needs Ayush (questions, approvals, overrides to confirm)
1. **Harness login (do first).** The macOS keychain copy of the Claude Code login is stale (its refresh token was already used; the refresh returned 400). I ran the runner with `ANUBIS_CC_CREDS_PATH=~/.cache/anubis/claude_creds.json`, the fresh login, good until about 13:50. The runner has now stopped (queue empty), and the next start without that variable will fail. Log in again with `claude` (or `scripts/anubis-auth setup`), or start the runner as `ANUBIS_CC_CREDS_PATH=$HOME/.cache/anubis/claude_creds.json .venv/bin/python scripts/master_queue.py resume`. master_queue reports this login failure as "usage limit". I did not touch the keychain or the harness code.
2. **Next approach (biggest decision).** On 7 of 7 tasks, wording-based traps did not catch fresh Opus. Precise rules get copied into code; imprecise rules break Never 6/11 or get flagged by QC (IN-16). Our pre-probe gates (fuzz on an old agent program, reflex gate) measured a spec change, not difficulty. Proposed: a blind fresh-agent read before any probe; config's pilot already matched probe 2 (19/19). See Proposed template changes.
3. **H7 wording.** Naming the amount and method in the H7 sentence (my 00:20 condition on your 4 hardens) is what let fresh Opus copy it: caldermoor da61544, tariff 0dd7a8c step 18, metered 9d220e4. The bare "by the same rule" form is the only H7 Opus ever missed, but QC calls it ambiguous (IN-16/W9). Decide whether H7 stays a lever family, and in which wording.
4. **Tariff r2 0dd7a8c: go or park.** It is idle at DIAGNOSIS READY (master_chat_work/20261025_tariff-engine-audit-repair/harden_r2/DIAGNOSIS.md, section 9 is the 07:17 addendum). It recommends Option B alone: N4, tier positions restart each month; 28.7% alone; the probe-2 program differs on 80/80 fuzz corpora. Optional: a check that a failed run leaves no partial invoices and exits non-zero. If the r2 probe still gets tests >= 95, it recommends parking at r3. Option A (bare recursive N1) is downgraded since caldermoor's recursive term leaked. The session lives on the worker server (stopped at the end of night mode): resume with `opencode -s ses_e8f53eb83ffeUY2Klj90QGF61h`.
5. **Overrides to confirm or reverse:**
   - district redesign r4 7743264, issued over the 3-round cap (it got tests 100 and is parked again);
   - caldermoor da61544 accepted despite its PILOT_WEAK reflex gate (probe 5 then got tests 98.45, parked);
   - metered r3 9d220e4: I held Phase 2 for you, a deviation from the policy go (it ended in ROUND LIMIT);
   - config parked after r2 ROUND LIMIT with r3 unused (override to spend r3).
6. **Parked tasks that reopen only on your override:** sentinel, sensor, district, caldermoor, metered, config, and match-replay (unchanged since QC v6 FINAL failed 3/0/1; TS-16 and CL-4 need test logic).
7. **QC watch items if any task reopens:** forgery is high on district (0.341), metered (0.336), sentinel (0.231) and tariff (0.205) against the old 0.05 target. Config NL-4 costs 59% alone, above the 25-45% band (CL-4).

## Results (harness runs, QC verdicts, gate status per task)
- 07:27 config harden r2 8e4df45: ROUND LIMIT, no credible lever. The NL-4 separating cases ship in products.ini and the env files. The agent rewrote the tool from scratch at step 16, so planted habits never ran. A blind fresh-agent pilot (rule text plus data head) got 19/19 right and also ruled out the best new candidate (K1, UTC-date retirement). Bundle untouched. Pilot in master_chat_work/20261025_data-product-config-compiler/harden_r2/pilot/.
- 07:19 metered harden r3 9d220e4 (LAST): ROUND LIMIT, no credible lever. The agent copied the amount-and-method H7 text straight into one helper and read the recursive billing group itself. Bundle untouched. Parked.
- 07:14 config probe 2 (after your harden r1 e317de1): tests 100 (34/35), rubric 100, overall 100. Genuine.
- 07:14 tariff harden r2 0dd7a8c DIAGNOSIS READY (master_chat_work/20261025_tariff-engine-audit-repair/harden_r2/DIAGNOSIS.md): all of N1-N3 were named by the contract (N1 is the 00:20 H7 sentence, copied into code at step 18). Option A: N1 as a bare recursive glossary term (needs you). Option B: N4 tier positions restart each month (28.7% alone). Its recommendation was A+B; after the 07:17 addendum it is B alone.
- 07:11 metered probe 3 (after your harden r2 e2dc50b): tests 100 (63/64; the negative did not fire), rubric 64.71, overall 82.35. Genuine. Fresh Opus got LV-MU-6, LV-MU-7 and LV-MU-5 right, although fuzz said your program would miss all three.
- 06:59 caldermoor probe 5 (after harden r3 da61544, the last round): tests 98.45 (51/57). The only positive missed was failed_run_leaves_no_partial_file; both N2 'wait' tests passed. Rubric 48, overall 73.22. Genuine. The glossary-only recursive term did not catch fresh Opus.
- 06:56 tariff probe 2 (after your harden r1 d62ffe6): tests 100 (31/33; 2 negatives did not fire), rubric 3.33 (the judge is real: only R8 earned), overall 51.66. Genuine. Fresh Opus got N1, N2 and N3 right.
- 06:41 district probe (attempt 9, after redesign r4 7743264): tests 100 (47/50; the 3 negatives did not fire), rubric 37.04, overall 68.52. Genuine. Fresh Opus got M1, M2 and M3 right, so the override round did not work.
- 06:31 sensor probe 3 (after redesign r2 4d6dfe8): tests 100 (28/30; the 2 negatives did not fire), rubric 75, overall 87.5. Genuine. Fresh Opus got all three new traps right (A, B, C).
- 06:16 sentinel probe 4 (after your harden r3 9aaa7c6): tests 100 (14/17; the 3 negatives did not fire), rubric 40, overall 70.0. Genuine (the staged copy matched the bundle). The r3 levers did not catch fresh Opus.
- 06:05 caldermoor harden r3 da61544 (LAST round) DONE: one new trap N2 'wait' (the longest blocking chain, defined only in the glossary; the expected miss reuses the chain_depth column). Reading it wrong alone costs 35% of test points and changes 299 of 300 fuzz cases. 57 tests and 13 criteria; stacking PASS, precheck CLEAN, 0 QC fails. Oracle 1.0 x3, nop 0, stub 0, forgery 0.196, but these are local tests-only runs: the worker's permissions block the harness. The worker marked it PILOT_WEAK only because old agent programs score 0.4485 against the 0.20 reflex limit. I overrode that: those programs predate the new rule. (Probe 5 at 06:59: tests 98.45, parked.)
- 05:45 sensor redesign r2 4d6dfe8 DONE: three new traps (A second-pass traverse closure, B set-out chain, C kept-shard district); one wrong costs 26.7% of tests (scores 0.733), all three wrong 0.198, reflex program 0.093; stacking PASS, QC 0 warns, precheck clean, oracle 1.0 x3, nop 0, stub 0.0116, forgery 0.070. Minor deviation accepted: R5 reworded so precheck passes. (Probe 3 at 06:31: tests 100, parked.)
- 06:00 harness back up after the login fix (district attempt 9, then sentinel, sensor, caldermoor, tariff, metered, config).
- 02:39 USAGE LIMIT: the district probe (attempt 6) failed with 'all 1 accounts exhausted' (reset about 05:40). The master chat and two workers stalled from 02:33 to 05:40, losing about 3 hours. The 05:50 and 05:57 resumes then failed on the stale keychain login (see Needs Ayush 1); fixed at 06:00.
- Your 4 harden sessions all finished DONE between 01:05 and 01:50: sentinel 9aaa7c6 (agent program 0.692, the target was a small honest miss), tariff d62ffe6 (0.181), metered e2dc50b (0.166), config e317de1 (0.175; NL-4 costs 59% alone, above the 25-45% band, so QC may flag CL-4). All have oracle 1.0 x3, nop 0, stacking PASS. Forgery: metered 0.336, sentinel 0.231, tariff 0.205. All 4 were probed 06:16-07:14 (results above).
- 02:30 district redesign r4 7743264 DONE: 50 tests and 12 criteria. Each single misread costs 26-38% of test points. Reflex gate 0.179, stacking PASS, QC 0 FAIL, oracle 1.0 x3, nop 0. Watch: forgery scores 0.341, because writing the shipped answers passes the 20 visible tests (old target 0.05); full QC may flag it. (Probe at 06:41: tests 100, parked.)
- 01:12 caldermoor probe 3 (attempt 4): tests 100 (50/55; the 5 negatives did not fire), rubric 13.64, overall 56.82. Genuine: the copy matched and there was no exception. The low rubric is conduct: no own extracts, long functions. Gate not met because only tests = 100 fails it.

## Decisions taken under NIGHT_POLICY (and round-limit overrides given)
- 08:13 idle check: nothing can run. Every planned task is parked or waiting on you (tariff r2 Phase 2). I started no new build or harden, because every trap shape leaked tonight and the next approach is yours to pick.
- 07:31 config PARKED one round early (r3 unused): the worker's blind fresh-agent pilot says no shape is credible. Override if you want r3 spent.
- 07:28 metered PARKED (r3 ROUND LIMIT, as the prompt said).
- 07:20 tariff 0dd7a8c Phase 2 HELD for you: Option A is your call, and the shape A relies on (caldermoor's recursive term) leaked in caldermoor probe 5. I asked the worker for an addendum only.
- 07:23 config -> harden r2 8e4df45, Phase 1 diagnosis only; Phase 2 waits for your go. The harness queue is now empty.
- 07:14 metered -> harden r3 LAST 9d220e4, Phase 1 diagnosis only. I am holding the Phase 2 go for you (a deviation from policy): it is the last round, and tonight's evidence says our pre-probe gates do not predict fresh Opus.
- 07:02 caldermoor PARKED: tests 98.45 after its last harden round. Config probe took the slot.
- 07:00 tariff -> harden r2 0dd7a8c issued and spawned (round 2 of 3; stops at DIAGNOSIS READY). It must say whether N1's explicit H7 wording gave the answer away; any bare-H7 proposal is marked for you. Metered probe took the harness slot.
- 06:43 district PARKED again: tests 100 after redesign r4. Tariff probe took the slot.
- 06:33 sensor PARKED again: tests 100 after redesign r2. Caldermoor probe took the slot.
- 06:18 sentinel PARKED: tests 100 after the last harden round (kill rule). Sensor probe took the freed slot.
- 06:08 caldermoor da61544 accepted despite the PILOT_WEAK reflex gate (old programs predate the rule; the mutant gate passed) -> stage probe, queued after sensor.
- 06:05 harness login fixed by env var (see Needs Ayush); probes queued in order district, sentinel, sensor, tariff, metered, config (2 at a time).
- 06:06 sensor 4d6dfe8 accepted -> stage probe.
- 00:20 (before night mode) intake: a9d62f3 match-replay parked; 5f2e150 caldermoor fix r2 clean -> probe.
- 00:48 night mode started: 2 workers + 1 harness, ramp 01:50 -> 4 + 2.
- 00:48 harness: caldermoor probe attempt 4 queued (tree c027b3b8bf2a).
- 02:20 caldermoor da61544 DIAGNOSIS READY -> go with one new trap, N2 'wait': the longest blocking chain, defined only in the glossary; the expected miss is reusing chain_depth. Gate: the mutant loses at least 25% alone on the real tests. Fallbacks N3, then N1; otherwise ROUND LIMIT and park.
- 01:52 limits raised: caldermoor da61544 spawned. The 4th slot stays free on purpose: the plan has no other task (match-replay, cohort, schema and vendor stay parked or killed, and no new build was queued).
- 01:42 district 7743264 DESIGN READY -> go with conditions. Three new traps: M1 grants shared again after a minimum-grant drop (27%), M2 allowance via a draws_from chain (30%), M3 credited relief = relief minus recovery (34%), plus carry-over between events. Predicted fresh Opus tests 70-80, but overall 66-71 sits partly above the 70 target. Risk: M2 may be too easy (a recursive lookup is natural code to write).
- 01:45 sensor 4d6dfe8 DESIGN READY -> go with conditions. Three new traps, each costing 26.7% of test points alone: A second-pass scale closure, B set-out chains, C district taken from the shard rather than the region column. Risk: C is a stated keyed rule, the kind earlier tests showed agents follow correctly, so it may not trip a fresh agent.
- 01:15 caldermoor: kill rule -> harden r3 LAST issued as da61544 (stops at DIAGNOSIS READY; one new trap of an untried shape; target tests 75-90). It starts when the worker limit rises at 01:50.
- 00:51 workers: 4d6dfe8 sensor redesign r2 (unparked), 7743264 district redesign r4 (unparked, override).

## Parked or skipped (and why)
- data-product-config-compiler: parked 07:31 after harden r2 ROUND LIMIT (r3 still unused).
- metered-usage-rating-pipeline: parked 07:28. Harden r3 found no credible lever after probe 3 got tests 100.
- caldermoor-commitment-closure: parked 07:02. Harden r3 (N2 'wait') got tests 98.45 / overall 73.22.
- district-heat-flex-procurement: parked again 06:43. Redesign r4 (the override round) got tests 100 / overall 68.52.
- sensor-network-lsq-correlated-adjustment: parked again 06:33. Redesign r2 got tests 100 / overall 87.5; the H7/H6/H3 shapes did not catch fresh Opus here either.
- sentinel-policy-recompute: parked 06:18 after probe 4 got tests 100 / overall 70.0 following harden r3, the last round. Reopening it needs your override, for example a redesign with a new trap shape, as district got.

## Proposed template changes (not applied; apply only after Ayush says ok)
- Config 8e4df45 already tried the blind fresh-agent read (OUT/pilot): 19/19 right, matching probe 2. It works as a cheap pre-probe filter.
- From metered 9d220e4 (strongest lesson tonight): fuzz on an OLD agent program only shows the rules changed, not that they are hard. Add a blind fresh-agent read to LEVER_RULES G10 before any probe: 3 fresh Opus get only the rule text plus a 5-10 line separating fixture, and a lever counts only if at least 2 of 3 miss.
- From sensor 4d6dfe8: prompts that say 'keep R1-R8 unchanged' should exempt the J4 code-quality criterion, because precheck's J4 check can force a rewording.
- From caldermoor da61544: the harden template's reflex gate should exempt agent programs older than the new rule, and Phase 3.4 should name the master as the one who runs the harness Docker block (the `*harbor run*` deny rule blocks workers even from writing that phrase in a command).
- From sensor 4d6dfe8: issue.py should not ask night workers for Harbor runs (their permissions block the harness CLI); they use a docker-only emulation instead.

## Still running at stop
- Nothing. No worker or harness run is active (since 07:27). Tariff r2 0dd7a8c is idle at DIAGNOSIS READY, waiting for your go (B alone recommended). The harness runner has stopped (queue empty). Night mode stopped at 08:30 (NIGHT_STOP file present).
- Your 4 windows (d62ffe6, e2dc50b, e317de1, 9aaa7c6) finished at 01:05-01:50; all 4 were probed tonight.
