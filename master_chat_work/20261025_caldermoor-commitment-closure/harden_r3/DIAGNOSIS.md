# DIAGNOSIS caldermoor-commitment-closure, harden r3 (da61544, LAST round)

Probe 3 (25 Oct 01:10, harness attempt 4, tree after 5f2e150): tests 186/186 = 100, judge 3/22 = 13.64, overall 56.82. Only tests = 100 fails the gate.

## 1. Phase A: GENUINE
- Staged copy `.kiro-staged-tasks/caldermoor-commitment-closure` vs BUNDLE, `diff -rq`: only `.kiro-staged-from` (harness marker) and `task.toml` lines 25 and 32, where the harness adds `"host.docker.internal"` to `allowed_hosts`. No BUNDLE file is newer than 24 Oct 23:56 (5f2e150 end), so the run used the current tree.
- `result.json`: `"exception_info": null`, reward 0.5682; agent 19:19:27 to 19:39:37 Z (20 min, 71 steps, $7.74). wrapper.log: "INTEGRITY: all 1 trial(s) completed cleanly; scores are trustworthy."
- No `Permission denied`, `Errno 13`, `Traceback` or timeout in `verifier/` or `trial.log`. reward-details: test_output 186.0 of 186 (each of the 50 positive checks scores 1.0, the 5 negatives score 0), judge 3.0 of 22.
- The judge read the response: its reasons quote trajectory facts, e.g. R4 "observed that no live edge combined a holding blocker with a non-holding dependent, but it did not construct ... dedicated test extract"; R11 fired on a randomized-hash claim made before later edits.
- Verdict: GENUINE. The tests score is a real 100.

## 2. Root cause
| cause | answer | evidence |
|---|---|---|
| 1 run error or wrong copy | NO | Phase A above. |
| 2 harness or rescoring change | NO | kit HEAD 976c1666 (unchanged); reward.toml 0.5/186 + 0.5/22 as built in 5f2e150; same harness wrapper and staging as probes 1 and 2. Probes 1 and 2 were both tests 100 (registry lines 78, 82, valid). No hard baseline existed to lose. |
| 3 our QC/fix rounds made it easier | PARTLY (H7 only) | Since probe 2 only 5f2e150 changed visible files: `commitment-protocol.md:207-210` (second share rewritten to name its amount and method, "every one of the distributable minutes is distributed again, in proportion to clamped effort by largest remainder ... across only the commitments that held fifteen or more"); `record-layouts.md` section 1 (blank or MALFORMED_ROW budget line skipped; no lever). Hidden-only: tests/test_output.py survivor fixture and six survivor tests, reward.toml, TRUTH.md. The rewrite was an honest W9/IN-16 fix ("by the same rule" had two readings), but it removed the only miss ever measured (probe-2 program 162/186). No rule figure or separating example was added to agent-visible data. |
| 4 levers weak by design | YES, PRIMARY | Every lever is one explicit sentence or table that a literal reader codes on first read (table below); the agent read all eight rule documents at steps 4-7 (19:19:43 to 19:19:53) and wrote every lever correctly in its single first draft at step 27; it never built a corpus that separates any lever, and still matches the reference on 300 of 300 fuzz corpora. |

Primary cause: 4. Contributing: 3 (the H7 rewrite).

### Cause 4 per lever
| lever | rule, where | step right | giveaway |
|---|---|---|---|
| A blocked set | dependency-semantics.md:50-51 "A commitment is blocked when it stands on no cycle and at least one live edge leaving it carries a block." | read step 5; coded step 27; step 61-62 checks states of the blocked set on shipped data | rule names only the edge and the blocker; a literal transliteration has no state filter. Self-test only on shipped data (no separating row, W5), so the right answer came from reading. |
| B periods_waived | cadence-register.md:58-69 first-match walk table; counts = periods taken per line | read step 6; coded step 27; step 37-38 sums and claim-vs-discharged check on shipped | first-match table is code-shaped (if/elif/else). |
| C (H6) allowance | cadence-register.md:49-54 one allowance of four per principal, drawn by every elapsed-period waiver in period-start then cadence-id order | read step 6; coded step 27; step 45 granted/lapsed sums | order and key stated together in one paragraph; key = principal is the obvious key for "each principal holds". |
| H7 second share | commitment-protocol.md:205-210 (5f2e150 wording) | read step 4; coded step 27 (step27_reconcile.py:1376-1388: `qualifying = [... shares[key] >= ALLOCATION_FLOOR]; shares = distribute(distributable, qualifying)`), unchanged in the final program (reconcile.py:1382-1387) | the rewrite names the amount ("every one of the distributable minutes") and the method, so there is no branch to re-enter. |

### H7 question (master): rewrite or own reading?
The rewrite. Evidence: (a) the probe-2 agent read the old wording ("the whole of the distributable minutes is distributed again by the same rule") and re-entered the fits branch; its program differs from the reference on 201 of 201 survivor-planting corpora and equals the H7 mutant byte for byte on all 201. (b) The probe-3 agent read the new wording at step 4 and wrote the correct second pass at step 27 in its first draft, before any test run. (c) It never self-tested the branch: shipped, eval and probe seeds plant no survivor month, and its only allocation check (step 58) replays one shipped month by hand. Its notes file (step 69) paraphrases the new sentence: "the whole distributable amount is shared again across the survivors, once". With one run on each side (n = 1 each), the wording explains the difference; nothing in the trajectory points to independent reasoning about the branch.

## 3. Lever table (reward-details + trajectory + fuzz)
Single-lever loss is measured on the current tests (WORK/fz/score_after1.jsonl, P = 186). Fuzz = OUT/fz/fz_h7_300.jsonl, 300 corpora (6 fix sets incl. survivor fixture, waiver mutation every third), reference = tests' `T.compute`.

| lever | checks the wrong reading fails (pts) | probe-3 earned | mutant differs from ref | probe-3 differs | probe-2 differs | verdict |
|---|---|---|---|---|---|---|
| A blocked set | 15 checks, 78 pts (allocation_and_load_hard, closure_and_blocked_hard, ledger_hard, edge_partition_hard, escalation, survivor x6, ...) | 78/78 | 300/300 (100%) | 0/300 (0%) | 0/300 on A artifacts beyond the H7 overlap | LEAKED (REVEALING) |
| B periods_waived | 16 checks, 81 pts | 81/81 | 300/300 | 0/300 | same | LEAKED |
| C (H6) allowance | 18 checks, 91 pts | 91/91 | 300/300 | 0/300 | same | LEAKED |
| H7 second share | 6 survivor checks, 24 pts | 24/24 | 201/300 (67%; 50/50 in every survivor fix set, 0/50 without) | 0/300 | 201/300 (= H7 mutant on all 201) | LEAKED for probe 3; HELD for probe 2 |
| envelope reserve (coupling) | amplifier | n/a | n/a | n/a | n/a | amplifier, counts 0 |
| negatives (5) | did not fire | 0 | n/a | n/a | n/a | correct |

All four levers are at 0% differing on the probe-3 program: under G10 every one is REVEALING.

## 4. Trajectory autopsy (B1)
- Read order: step 3 `ls`; step 4 protocol; step 5 identity register, precedence charter, dependency semantics; step 6 cadence register, record layouts, glossary; step 7 output contract (all eight documents in 20 s). Steps 8-26 survey the data (heads, manifest revisions, legacy widths, alias folding, registry, events, cadence register), 19:19:57 to 19:25:10.
- Program: step 27 (19:28:39) creates reconcile.py, 1495 lines, in one write; steps 28-33 are small fixes; first run at step 34. Final program 2015 lines; the graded logic for A, B, C, H7 and the reserve is unchanged from step 27.
- Self-tests (steps 35-70): determinism with a randomized hash seed (35), sums and partitions on shipped outputs (36-37, 45, 58, 65-66), claimed waivers vs discharged periods on shipped data (38), allocation never above effort (41), desk contenders (42-43), byte format (46), a randomly mutated copy (51), empty extracts (52), junk output dir (53), brute-force cycle check on random graphs (55), shipped allocation replay (58), states of the blocked set (61-62), publish, rerun and data md5 (67-68), fresh-directory rerun (70). No self-test built a case that separates A, B, C or H7; it checked that the shipped extract has none (steps 38, 62).
- Time: read 20 s, survey 9 min, write 3.5 min, check and publish 11 min.
- Pattern (same as LEVER_RULES section 0): it reads every rule, transliterates each sentence with the field the sentence names, writes once, never changes the graded logic.

## 5. Reflex program
`OUT/agent_program/`: probe-3 final `reconcile.py` (76 KB, 2015 lines) and its 28 shipped outputs, from the run artifacts `/app/out`. Copy for the fuzz: `OUT/fz/progs/agent_p3/reconcile.py`. The probe-2 program is in `OUT/fz/progs/agent_p2/`.

## 6. LEAK_LIBRARY rows
| lever | how it was written | leaked at | planned fix |
|---|---|---|---|
| CM-A blocked set | one predicate sentence naming only the edge and blocker (dependency-semantics.md:50-51); shipped data has no separating row | step 5 read, step 27 code | keep (it still amplifies other slips); no rewrite, the master forbids rewriting A/B/H6/H7 |
| CM-B waived periods | first-match walk table (cadence-register.md:58-69) | step 6, step 27 | keep; code-shaped tables are not levers (LEAK_LIBRARY V0-1) |
| CM-C allowance (H6) | key, order and tie in one paragraph (cadence-register.md:49-54); key = the principal the sentence names | step 6, step 27 | keep; an H6 key must differ from the key the sentence names |
| CM-H7 second share | after 5f2e150 the sentence names amount and method (commitment-protocol.md:207-210), so there is no early-exit branch to re-enter | step 4, step 27 | keep (W9 fix is required); an H7 lever survives only while a stated rule reuses a procedure that has an early exit |

## 7. Lever plan for Phase 2 (for master review)
One new independent lever of an untried shape; A, B, C, H7, the five negatives and the H7 wording stay as they are.

### N2 (primary): "wait", a recursive chain quantity (H6 along a recursive chain + H3 defined term differing from a per-line output field)
- Rule, one clause, no contrast and no example (W1, W3, W6). Its home is the glossary (or the dependency-semantics section 4 enumeration): "**Wait** The wait of a commitment that is not blocked is zero, and the wait of a blocked commitment is one more than the greatest wait among the blockers of the blocking edges leaving it."
- Use (W2: a different file from the definition): commitment-protocol.md section 9, reserve blocked term: "thirty minutes for each unit of the wait of every line of `blocked_commitments.csv` whose commitment ..." (wait 1 = today's 30 minutes per line, so shipped outputs stay identical where wait = 1).
- Reflex misread: reuse the per-line output field `chain_depth` (greatest of the fewest-hop distances, the BFS the agent already writes for blocked_commitments.csv, which also counts hops through cycle members and terminals). The rule never mentions chain depth.
- Why it is a fair, single-reading rule: well-founded recursion (blocking edges among blocked commitments form a DAG; cycle members and terminal blockers are not blocked, so their wait is 0). One reading.
- Separation (measured with OUT/proto/wait_stats.py on 6 hidden seeds): wait differs from chain depth for 10-14 blocked commitments per seed, all with depth > wait (closures that run through cycle members or unblocked holding nodes); the reserve moves in 10-14 principal-months per seed, allocation in 3-7. That is thin, so a G12 fixture plants diamond shortcuts (X->Y->Z->T plus X->Z gives depth 2, wait 3) on the hidden seeds, inside every stated bound, so both separating sources appear.
- W5: the shipped extract separates 2 of 156 blocked commitments; extend `_SHIPPED_DROP` to remove those edges from the shipped seed only, then apply common rule 6 (re-embed `_SHIPPED_DATA`, reward.toml, TRUTH sha).
- Grading: COUPLING through `reserve_minutes` (month_load_index) into allocation, ledger, queues, lineage, rollups, escalation, audit and manifest; add one owned-row family `wait_reserve_exact` (w3) and `wait_reserve_hard` (w5) on the planted seed (month_load rows of the planted principal-months). Target alone 25-45% of test points (CL-4, no cliff); measure with a single-lever mutant (chain_depth used in place of wait) and with the probe-3 program; the fuzz on the probe-3 program must differ on more than 0% of corpora, and a shrunk corpus goes in OUT/proto/.
- Judge: one w3 conduct criterion: "The agent independently recomputes the wait of every blocked commitment in an extract it built, outside its program, and compares the reserve its program used for each principal and month." solve.sh self-check prints `check R13 ok`.
- Risk: the definition is literal and Opus may code the recursion exactly (memoized), giving 0% difference. Mitigation: the definition sits in the glossary, away from section 9 and from blocked_commitments.csv; nothing pairs it with chain depth; both separating sources are planted. If the fuzz on the probe-3 program is still 0%, N2 is REVEALING.

### Fallbacks (only if N2 fails the fuzz or the cost gate)
- N1 (H3): "block day", the commitment day of the earliest blocking edge's `asserted_at`, keys the reserve's blocked term in place of the commitment day. Shipped separates 142 of 156, so it needs a shipped-seed generator constraint (heavier, risks W5 and data drift).
- N3 (H6 keyed wider than the line): a holding blocker carries the block of at most N dependents, drawn in a stated order. The key is the blocker, wider than the dependent line. Interacts with A; shipped fan-in above 1 for 15 blockers needs dropping.
- Overlap check: none of N1-N3 reuses another live task's entity and mechanism (tariff, config, metered, sentinel, sensor and district list in the master notes).

If neither N2 nor a fallback reaches more than 0% differing and at least 25% alone, the report will say "ROUND LIMIT: no differing lever".

## Lessons for the master
- An H7 lever cannot survive its own W9 fix: once the rule names the amount and the method there is no branch left to re-enter (probe 2 missed, probe 3 right at step 27) | no change: record in LEAK_LIBRARY
- A fresh agent's self-tests only confirm that shipped data has no separating case (steps 38, 62); hidden-only cases hold only when the rule text itself invites a different computation | no change: LEVER_RULES 1b already says this
- The fuzz on the probe-3 program found 0 of 300 corpora differing for all four levers, which flags REVEALING levers more cheaply than a probe | template_change: harden template Phase 1 should run the G10 fuzz on the newest agent program by default
