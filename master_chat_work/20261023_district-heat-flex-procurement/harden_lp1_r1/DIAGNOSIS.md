# P9 harden lp1 r1 diagnosis: district-heat-flex-procurement (board 0154d63)

Written 23 Oct 2026 IST. Phase 1 only, before any BUNDLE edit. Harness HEAD 71a653b23fc2.
RESULT: `traj_a4/trajectory_job_district-heat-flex-procurement_0ee2e7/`, claude-opus-5 Run 1: tests 100.0, rubric 100.0, combined 100.0.

## 1. Phase A: the 100 is GENUINE
- The run copy is the current BUNDLE. `logs/job-config.json` points at `.kiro-staged-tasks/district-heat-flex-procurement`. `diff -rq` of that copy against BUNDLE shows only `.kiro-staged-from` and `task.toml` lines 25 and 32 (`host.docker.internal` added to allowed_hosts by the harness judge proxy). `agent/instruction.txt` is byte-identical to `instruction.md`.
- No errors: Run 1 `result.json` exception_info None, verifier reward 1.0. The 4 negatives did not fire and the 28 positives scored 1.0. job.log, trial.log and finalize.log show no error. The only lines are usage-upload notices.
- The judge read the response. `judge_response.txt` quotes the closing reply for R1 to R6 (e.g. "states that summary.json has global credit_cents = 1959002") and cites trajectory step 15 for R10.
- The run took 12m51s (19:28:01 to 19:40:52 UTC) in 29 steps, well under the 7200 s timeout. The earlier timeout/build failures are gone because round 2 dropped the 30 s size lever.

## 2. Lever table (reward-details.json plus trajectory)
Agent sequence:
- step 3 `cat schema.md` (the whole file);
- steps 4-7 read every data file and checked neutrality properties itself: step 7 "relief mod10 [(0, 108036)]", every Wh is a multiple of 10;
- step 10 wrote the program (step 8 failed only because /app/out did not exist);
- step 11 ran it;
- steps 13-14 cross-checked all 2000 groups against an itertools.product brute force ("bad 0");
- steps 15-16: one fix, classifying profile rows of orphan offers by range/duplicate. This was triggered by schema.md L56-58 "Rows of orphan offers ... are sorted into kinds the same way";
- step 19 checked identities ("ALL CHECKS PASS");
- steps 22-24 ran a synthetic extract with wh_per_tick 4, `[export]` default, unknown region ZZ, a duplicate and an out-of-range profile row, an orphan offer and a cooldown site.

The logic was never changed after step 16.

| Lever (check weight) | Rule location | What gave it away | Right at step |
|---|---|---|---|
| H1 compliance ranking (waiver_labels_case 3 + composed) | schema 2.6 L127-134 | Ranking as one plain list next to the waiver definition | 10 (program), 24 (synthetic cooldown) |
| SIGNEDY `[export] waiver_signed = Y` decoy | schema L23-24 "Any other section ... carries no rule" | The decoy is refuted in plain words in the same file description. The closing reply calls it "export-tool noise" | 10 |
| H2 greatest sorted tuple (tie_break 3 + composed) | schema 2.4 L116-119 | One sentence. Self-test: the brute force at step 14 uses `if tb>bestsel` | 10, 14 |
| H3 cap after uplift (cap_after_uplift 3 + composed) | 2.5 L124-125 + 6 L194 | "after every adjustment" plus the cap-binding formula written out | 10, 12 (checked base+uplift vs cap on shipped cards) |
| H4 descending-id residual (residual_ties 3 + composed) | 2.4 L120 "served in descending identifier order" | Plain sentence | 10 |
| H5 per-value ticks, per-site credit rounding | 2.3 L108-112 | The rule states its trap ("as soon as it is read, before it is added to anything"). Step 7 checked mod 10 neutrality | 10 |
| DH-2 ticks in the search (tick_feasibility 3) | 5 L161-164 "relief ticks" | Plain sentence | 10 |
| DH-3 funded pool (composed only) | 7 L198-202, calculation order spelled out | An explicit ordered list | 10 |
| DH-4 rejected rows (rejected_profile_rows 3, unknown_region 3, composed) | 1 L47-58, L38-42 | Numbered kinds plus a trap sentence (L56-58) | 15-16 (only fix), 24 |
| DH-5 waived weight doubled via label (composed) | 7 L205-206 | Plain sentence | 10 |
| DH-7 component order (objective_component_order 3) | 5 L166-179 | Numbered list | 10, 14 |
| Shipped format (4 x 1) | 8 | Plain | 11 |
| Judge R1-R6 figures (18) | instruction asks for them | A correct program prints them | 28 |
| Judge R7/R8 code shape, R9/R10 negatives | n/a | Clean code; the cross-check really was shown | 28 |

## 3. Cause
The same as the cohort section 0, cause 4. Every rule is one explicit sentence in schema.md, read in one `cat` at step 3, and several of them state their own trap:
- L56-58 rows of orphan offers;
- L141-142 "an authorized site on safety hold or in cooldown keeps its candidate offers";
- 2.3 "before it is added to anything";
- L318-320 "including lines skipped for an unknown-region site".

The agent wrote the program once, brute-forced the search, and ran one synthetic extract covering the rejected-row family. The hidden composed extracts only repeat rules the agent coded correctly the first time. The 72-point whole-document design had nothing to separate. The judge "states figure X" criteria pay any correct program.

## 4. Reflex program
`OUT/agent_program/derive_report.py` (722 lines) is copied from `Run 1/artifacts/app/out/derive_report.py`. It is the step 5 reflex program for STACKING_CHECK (c).

## 5. Direction (per LEVER_PLAN_v1 and the prompt)
- L1: a green export receipt. A new `export_manifest.tsv` holds per-file record counts and written-field sums, described in its own header as a receipt only.
- L2: a make-it-match repair. A per-row `register_multiplier` in profiles.tsv is stated in the profiles.tsv description of schema.md section 1. Under the correct reading the receipt's relief/recovery sums no longer equal the agent's converted energies, and dropping the multiplier makes the receipt match again.
- L4: the effective rate composed from rate_cards.xml (`override` in place of `base`, stated in the XML header comment), events.json (uplift), program.ini (`[segment_rate_adders]`, stated in the ini comment) and the cap convention 2.5.
- L7: a per-interval credit rounded half to even, stated in the rate_cards.xml header comment. The 2.3 money sentence is removed.

Old trap-explaining sentences are removed (W1). Judge figure criteria are deleted (J1), and the closing-reply figure ask is removed from the instruction.
