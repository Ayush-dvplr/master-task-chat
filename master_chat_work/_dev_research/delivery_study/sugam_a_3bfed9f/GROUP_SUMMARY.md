# GROUP_SUMMARY sugam_a (board 3bfed9f)

Repo HEAD `2dfb1f8f7b86db305b1f6afa63279873e6e918e4`. Session renamed (opencode `ses_e8e7e88e1ffeQUKseVa1z7xSbM`). Work was read-only; nothing was executed except `stacking_check.py`.
Units: "genuine test pts lost" means percentage points of the tests score (100 = all positive test weight), not raw weight.
Per-task evidence is in `A_<task>.md` and `C_<task>.md` in this folder.

## 1. Table

| task | verdict | overall / tests / rubric | genuine test pts lost | main lever shape |
|---|---|---|---|---|
| 4a5f9738 (spectrum register, 3-axis union measure) | GENUINE | 38.99 / 23.88 / 54.1 | 76.1 (51/67) | Many per-row rules (about 8), each shifting a few rows inside whole-block equality checks. The largest is a definition ("a layer supplies a group when its record carries values") that the agent narrowed by treating a semantic flag (action=note) as "no data". Shipped evidence residue fits that narrower reading (C_4a5f9738 L-a, NEW) |
| 4ee62df1 (config pipeline + tool repair) | PARTLY | 48.99 / 20.62 / 77.36 | 63.9 (62/97); another 15.5 lost to an unstated `_real_work` gate | Scope by omission. Only the zone branch says "replay only that zone's ops". The base branch's validity rule lists every env as valid, so the agent replayed zone ops into the base spine. That upstream error moves a hash-folded shift, which cascades into every aggregate |
| 8da8ba3d (security config + tool repair) | GENUINE | 61.92 / 77.68 / 46.15 | 22.3 (25/112) | A silent arithmetic fault in shipped code with no internal contradiction (`+` where `*` was meant), graded by 4 checks (20 pts). Also a working comment format the agent "improved" away (5 pts) |
| 9bbcb50f (sales transform) | ARTEFACT | 67.69 / 58.46 / 76.92 | 0 confirmed (4.6 unresolved) | Version skew. The graded contract had no tariff-epoch rules, which were added to the folder after the run (A_9bbcb50f) |
| a5b17048 (repo repair, ledger parser) | ARTEFACT | 67.41 / 42.5 / 92.31 | not determinable (0 confirmed) | The hidden test file, with an embedded reference package, shipped inside `/app/repo/tests`. The agent copied that reference. The run was graded by an older, different verifier (A_a5b17048) |

## 2. Test-design patterns ranked by genuine test points they caused to be lost

| # | pattern | mechanism | how graded | how it passes QC | tasks / pts | SAFE/RISKY |
|---|---|---|---|---|---|---|
| P1 | Whole-block exact equality over every row of a view | One upstream misreading moves a few rows in many blocks, and every block fails | `_same` = sorted-key JSON equality per block (4a5f tests :2902); whole-file equality (4ee6, 8da8 :388/:410/:419) | QC treats positive cascades as legal (QC_RULINGS:125: TS-26/AL-28 failures "were all on negatives, never on positive cascades"). 4ee6 states the cascade in the instruction (:11, :31), which is the CL-4 kit exemption (PLAYBOOK:51) | 4a5f 76.1, 4ee6 ~44 direct, 8da8 15 | SAFE |
| P2 | Anchored mirror views | The primary artifact must match the reference on 45 of 50 items. Mirrors are then compared to the agent's own primary, so one row error costs one check and an upstream error costs the family | `_anchor` 4ee6 tests :530-546 | One observable per check (TS-26). The family loss is announced by an instruction sentence | 4ee6 19 | SAFE |
| P3 | Value from the agent's own deliverable folded into every expected number | A shift = f(config value, reject count, sha of the agent's zip). Any upstream slip moves every aggregate | `rekey_shift` 4ee6 :475-482 | Stated in the contract (Z-shift section), and the instruction says an error anywhere moves every bound | 4ee6 (inside P1/P2 totals) | RISKY (CL-4 amplification relies on one sentence) |
| P4 | One scalar graded by several whole-doc checks plus an invariant "law" check | One wrong value fails config, two profiles and the law check | 8da8 :388, :410, :419, :445 | Passed as a positive cascade. There is no whole-doc sentence, so it is a CL-4 exposure | 8da8 20 | RISKY |
| P5 | Silent fault in shipped code with no contradiction cue | The instruction names only fault classes. The decoy faults have contradiction cues (a second code path or a field name); the real one does not | Fixed literal expected values (8da8 :104-190) | Passed IN-15/IN-16 by "interaction rules each file declares through its own field values" (instruction :29-31), with no settling text | 8da8 20 (same pts as P4) | RISKY |
| P6 | Format carried only by working shipped code | Opus rewrites an emitter it finds ugly, and the test regex no longer matches | `^# score=` regex sum (8da8 :691) | Not challenged at QC. TS-19 "stricter than contract" risk (QC_RULINGS:46) | 8da8 5 | RISKY |
| P7 | Reference implementation at test time over embedded inputs | All shipped files are embedded as zlib/base64 blobs. Expected values are recomputed in the test, and nothing on disk can be copied | 4ee6 `_BLOBS` :63-121, docstring :1-7; 9bbc current version same | Treated as "independent re-derivation" (G9) | carrier for 4ee6 | SAFE |
| P8 | Embedded seeded generator for hidden tiers, plus literal expected values | Hidden corpora are built at test time from a generator inside the test file, and the agent's program is rerun on them | 4a5f `_load_generator` :1108-2870, `_heldout_all` :3104; 10/67 pts | TS-19: the generator stays in documented bounds | 4a5f 14.9% weight (failed) | SAFE |
| P9 | Rules induced from evidence files, graded once in their own block | Withheld rules must be voted from observation files | 4a5f `policy_withheld_rules_exact` :3153 (w5) | IN-15 is met by "settle from the corpus" (instruction :22-23) | 4a5f 0 lost: the agent solved them | SAFE, but it did not separate |
| P10 | Program rerun as `nobody` via setpriv, with input-mutation snapshot, /tmp scan and narrow negatives | Anti-cheat. Negatives fire only on exact acts (sha of the shipped broken file, an expected literal in a named function body) | 4a5f :2879-3061; 8da8 :293-309, :957-1004 | TS-16 narrow; AL-28 distinct acts | 0 lost (no negative fired in any task) | SAFE |

Each pattern counts points once. The 4ee6 15.5-point gate (`_real_work`, tests :553-562) is not a pattern to adopt (see section 5).

## 3. Leak-avoidance patterns (with the LEAK_LIBRARY row each would have fixed)

| # | pattern | evidence | fixes LEAK_LIBRARY row |
|---|---|---|---|
| LA1 | State the scope restriction only on the narrower branch. The main branch carries an enumeration that admits every case, and the trap is never named | 4ee6 contract :19 "its `env` is listed in `journal_envs`" vs :37-39 "whose `env` is that zone ... against that zone's own state"; agent traj step 25 | CR-1 (trap spelled "not only the one...") and STATE (exception in its own sentence, W3) |
| LA2 | Put the separating cases only at the tail of a long stream, interleaved, with byte-level decoys (homoglyph env tokens) on the same lines to absorb attention | 4ee6 journal: base 9006 ops, zone ops at seq 9001-9034 with decoys `сore`, `Core`, `edge\u200b`; the agent handled the decoys and missed the scope | vendor RUN (separating stream shipped next to the rule, W5) and CR-2 (decoy refuted on the same page) |
| LA3 | A bare definition with no carve-out, plus shipped evidence whose residue fits a narrower reading | 4a5f precedence_policy.md:3-4 "supplies a field group only when its governing record carries values"; agent traj step 62 "a note carries no decision ... recognising this removes all 188" | CR-3 (one sentence, no alternative reading). Here an alternative is invited by data, not by text |
| LA4 | The instruction names fault classes only. Contradiction cues exist for the decoy faults, not for the real one | 8da8 instruction :2-3 "faults in argument routing, key normalization, and derivation arithmetic"; agent final step 40 "it has no internal contradiction ... so I had no evidence it was injected" | ESC/EXT (trap explained, W1) and SALV (both reflexes named, W1) |
| LA5 | A scope clause at the end of a long sentence, with no example | 4a5f duty_policy.md:31 "whatever became of that grant". The agent's carry resets were 336 vs 281 (INFERRED link) | V0-2..V0-8 (single explicit sentences) |
| LA6 | Rules spread across many spec files (11 in 4a5f), each in the file that governs the data; the instruction states no rule and says "follow it to the letter" | 4a5f instruction :13; 11 md specs | common cause "split across only 2 files pointed together (L4)" |
| LA7 | No shipped expected output and no worked example; samples declared hints only | 8da8 instruction :19; no expected out in any GENUINE/PARTLY task. The agent's self-tests were only determinism, identities and bounds (4a5f steps 42-61; 4ee6 35/39/44; 8da8 33-37) | CR-1/V0 rows where shipped boundary rows let the agent watch the rule fire (W5/W6) |

## 4. Differences from our LEVER_RULES (both directions)

They do things our rules forbid or do not mention:
- **Hidden or unflagged rule.** 8da8's multiplicative pbkdf form is stated nowhere visible (only TRUTH.md:30-33). Our never-used list (LEVER_RULES:24) forbids hidden rules, yet this passed QC. QC_RULINGS IN-15 (two readings, nothing settles) should have caught it.
- **Hidden reruns below G3's 30%.** 4a5f puts 14.9% of weight on hidden tiers, 4ee6 about 5% (`cli_reproduces` only), 8da8 0%. They still separate, because no shipped expected output exists for self-checking. Our G3 assumes the agent can self-check shipped data. Here it cannot.
- **Same-fact stacking on positives.** 8da8 grades one scalar in 4 checks (P4) with no whole-doc sentence, against our G1/CL-4. 4ee6 makes every aggregate depend on the agent's own zip hash (P3). Our G1 does not mention this.
- **Unstated gate.** `_real_work` (4ee6 :553-562) is called inside 5 format checks (:1133, :1144, :1157, :1166, :1234). Our G2 ("each test asserts own rows, no early return") forbids it.
- **Judge clauses the oracle fails.** 8da8 R1 (judge.toml:14), R2 (:27) and R8 (:105, .pyi stub) are not in solve.py. Our J2/JD-7 forbid this.
- **No assertion messages.** All `test-stdout.txt` files print only the reward. Our G7 asks for messages.
- **Not in our map, new Opus behaviours:** (a) Opus repairs only faults it can justify by a contradiction, and says so (8da8 step 40). (b) Opus narrows a definition using a semantic flag and validates the narrowing against evidence residue (4a5f step 62). (c) Opus rewrites working emitters it finds untidy (8da8 step 27).

Our rules confirmed:
- Sec0: Opus wrote the program once and never changed graded logic. In 4a5f the first full run was at min 17, with only an as_of override afterwards (step 47). In 4ee6 the cli was at min 13 with no graded change. In 8da8 the edits were at min 5-6 with no later change.
- Sec7 pilot lesson: one lever costs more than 30% only through a whole-doc cascade. 4ee6 lost 64 pts from one scope misreading through P1-P3.
- L6/H3 (scope via definition) matches 4ee6 LA1 and 4a5f LA3/LA5. W1/W2/W3/W6/W10 are all observed.

Things we do that they do not: weight-1/3/5 coupling tables (G10), rule-coverage mutants (G11/AL-27), generator bound asserts (G12), and literal-reading self-test design (W9). None of these appear in 8da8. 4ee6 has only one private-corpus rerun.

## 5. Anti-patterns and artefacts

- **Version skew (9bbc, a5b1).** The folder content changed after the run: one "Accept and mask" commit on 2026-10-24/25, while the runs were on 2026-10-22/23. The recorded board scores do not describe the current folder. Rerun before using them as delivery evidence.
- **Hidden test file shipped in the environment (a5b1).** `/app/repo/tests/test_output.py` (3288 lines, with `_REFERENCE_PKG`) was readable by the agent (steps 6-17), and the agent decoded the reference (step 12).
- **Score aggregation mismatch (a5b1).** verifier `reward.json` gives 0.758 while `score.json` gives 67.41 (judge 1/66, test 1/160 weights in reward-details).
- **Unstated gate (4ee6).** `_real_work` cost 15.5 pts on checks whose own property the agent met.
- **Same-scalar stacking without a whole-doc sentence (8da8).** 4 checks, 17.9 pts on one value.
- **Judge clauses the oracle does not meet (8da8).** R1, R2 and R8 cost judge points, not test points.
- **Misread negatives keyed to one literal wrong figure (4a5f :3290-3342).** They never fired and give no separation.

## 6. Open questions for the master

1. Is "silent fault in shipped code with no contradiction cue" (P5) acceptable to our QC under IN-15/IN-16? If yes, what visible carrier makes it settle-able without leaking?
2. Should G3 (hidden reruns at least 30%) be relaxed when no expected output is shipped? Here separation came from shipped-input checks.
3. Is evidence residue that fits the wrong reading (LA3) an IN-16 defect or a legitimate decoy?
4. Should 9bbc and a5b1 be rerun before they count as delivery examples, given the version skew and the leaked hidden test?
5. Is a hash of the agent's own deliverable folded into expected values (P3) acceptable under CL-4 when one instruction sentence announces it?

## Lessons for the master
1. Separation came from upstream readings that cascade into whole-block exact checks (P1-P3), with no shipped expected output to self-check against. It did not come from more rules.
2. The strongest single levers were scope by omission (scope stated only on the narrow branch) and a definition narrowed by a semantic flag that the data invites.
3. Opus fixes only faults it can justify by a contradiction: one uncontradicted shipped fault survived, but it is a hidden-rule QC risk.
4. Of the 5 delivery tasks, 2 are ARTEFACTS (version skew, leaked hidden test). Delivery scores need a rerun check before they are copied as evidence.
5. Our G3 (hidden reruns) and G10 (coupling tables) were absent here and not needed. Our G1/G2/JD-7 bans were violated and still passed QC.
