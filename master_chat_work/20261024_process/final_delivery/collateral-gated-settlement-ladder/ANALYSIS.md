# ANALYSIS: e08c051f-cce9-5aba-b20d-88fb75574b6c (board 9bd1ca1)

Delivered folder `Anubis_Tasks_Samples/Final_Delivery/e08c051f-cce9-5aba-b20d-88fb75574b6c/`. Scratch copy `/tmp/fd-collateral-gated-settlement-ladder-20261024T1156/`. Docker: `docker ps` was empty at 11:56 IST, so I built my own verifier image (`fdcgsl-verifier:local`) from the copy and ran solve.sh and the test checks in it. I never ran the LLM judge.

## Verdict

**GENUINE (amplified).** Opus lost 55 of its 55 lost test points, plus 3 judge points, to one mistake. Its transform turned the 40 `amount_minor` values written as quoted strings in `adjustments.jsonl` (for example `"-104527"`) into integers and accepted them. The agent-visible contract forbids this twice: schema.md:34-35 "`amount_minor` must be a JSON integer" and schema.md:148-149 "an `amount_minor` that is not a JSON integer" is malformed. The agent read that contract in step 4 and saw the 40 strings in its own census in step 11. Then at step 26 it wrote a branch on purpose to coerce them (agent transform.py:504-514). Removing only that branch in a copy brings the tests to 79/79, and the closing carry-forward count moves from 397 to 395, which also wins back judge R3 (`regrade.txt`, patch proof). The other 3 judge points are R15, a process criterion that no file asks for (CONDUCT). Nothing in the loss is an artefact, a judge error or a hidden rule. But the depth of the score comes from design amplification, not from many traps. One yes/no decision fails 11 whole-document tests, because the strict test compares the full event set even inside the per-rule tests. The tests score bimodally (30.38 or 100). An older, independent Opus run on the pre-masking copy made the same decision through a different code path and scored the same 30.38. That run is in the peer files.

## Phase 1: identity, provenance, integrity

### 1.1 Mapping and diffs
- `Final_Delivery_Internal/mask_map.json`: identifier `e08c051f-cce9-5aba-b20d-88fb75574b6c` <-> slug `collateral-gated-settlement-ladder`, source `Perfect_for_Delivery/Poonam_Chourey/...`, 5 rewritten files, 28 replacements, host paths rewritten to `/delivery/...`. Confirmed. Author: task.toml:9 `Harsh Gupta`. Category: task.toml:12 `Data Processing`. QL folder: `Perfect_for_Delivery/Poonam_Chourey/` holds only the QC report .md, no bundle.
- Older copy `Pass@1_New/Poonam_Chourey/Harsh Gupta/collateral-gated-settlement-ladder`. `diff -rq -x trajectories -x output` against the delivered folder shows 4 files changed:

| file | change | why it matters |
|---|---|---|
| task.toml:5 | name slug -> masked id | masking |
| solution/TRUTH.md | title slug -> id (l.1); provenance uuid/slug -> id (l.548-550); "positive total 61" -> "57" (l.268); R10/R12 +5 -> +3 (l.279, 281); range -8/61 -> -8/57 (l.570-571) | masking plus the QC reviewer's reweight |
| tests/judge.toml | R5, R8 type "factuality and hallucination" -> "task completion"; R10, R12 weight 5 -> 3 and importance critically_important -> important; R14 "instruction following" -> "agent behavior" | QC fixes JD-14/JD-15/JD-16, "applied by QC reviewer, not committed" (QC report l.35-37) |
| tests/reward.toml:4 | judge weight 0.5/61 -> 0.5/57 | follows the reweight |

  **The recorded Opus run was graded on the OLD judge** (reward-details judge weight 0.00819672131147541 = 0.5/61). The delivered judge scores the same verdicts 51/57.

### 1.2 Masking residue
`grep -rniE 'collateral-gated|harsh|gupta|poonam|chourey|/Users/|kiro|macbookpro'` over the delivered folder:
- `environment/data/schema.md:1` "# FY28 collateral-gated settlement ladder: the written contract". The agent can see this line and it is almost the slug word for word, so it **de-masks** the task. It also appears in the trajectory (the schema read in step 4 and the agent's transform docstring, `artifacts/app/out/transform.py:2`).
- `task.toml:9` author name and email (expected metadata).
- `tests/test_output.py:83, 87`: false hits inside the base64 blob.
- No `/Users/`, `.kiro-staged` or `macbookpro` remains. `config.json` shows the API key already masked (`478a****4f9`).

### 1.3 Leaks in environment/
`grep -rniE 'trap|lever|grader|hidden|answer|expected|verifier|oracle|solution|truth|test_output|reward|judge|rubric|decoy'` over `environment/` finds only schema.md:158 "is judged on the rows of that file as they stand" and :189 "are judged against the balance...", which is ordinary English. The closing figures (13292764300, 685349, ...) appear only in solution/TRUTH.md and tests/judge.toml. **No leak.**

## Phase 2: kit verdict

### 2.1 precheck (kit 71a653b2 + our extras), copy without trajectories (`precheck.txt`)

| block | pass | warn | fail |
|---|---|---|---|
| structure_qc | 17 | 0 | 0 |
| instruction_qc | 5 | 0 | 0 |
| tests_qc | 37 | 0 | 0 |
| judge_qc | 19 | 0 | 0 |
| our extra checks (gaps, author notes) | none | | |
| caps | tests 22, judge criteria 19 (judge +57 / -8) | | |

Last line `PRECHECK CLEAN`, exit 0. Fails 0, minors 0, warns 0.

### 2.2 Against the team QC report (PASS 0/0/0, re-QC of 05f2f8ea, 2026-10-23)
| QC finding | how resolved | live kit today |
|---|---|---|
| JD-15/CL-2 fail: R1-R9 lacked expected values (l.31) | each R1-R9 now carries the exact figure; forgery price 31/61 -> 0 | judge_qc clean |
| TS-16/CL-5 warn: network/process ban unstated (l.32) | stated in instruction.md:21-23 | clean |
| TS-27 warn: nondeterminism negative (l.33) | negative now runs the transform twice (test_output.py:948) | clean |
| JD-15/JD-16 labels R5/R8/R14 (l.35) | relabelled by the QC reviewer, not committed | clean |
| JD-14 R10/R12 weight (l.37) | 5 -> 3 by the QC reviewer, not committed | clean |
| JD-8 minor R10/R12 overlap (l.22, 197) | accepted as "read the method" | not flagged |
| AL-8 (expert 480 min vs agent budget), TS-2 (tests image not digest pinned) (l.41) | withdrawn | not flagged |

The tasker accepted no warns. Every warn was fixed or withdrawn, and our live kit agrees (0/0/0).

**Where the delivered task breaks OUR rules yet was delivered:**
| # | our rule (file:line, quoted) | evidence in this task |
|---|---|---|
| B1 | `_COMMON_RULES_v3.md:48` J1 "no criterion whose only content is a number from TRUTH.md or the agent's own figure"; `P2_build_v3.md:91` "J1 no 'states figure X' criteria"; `LEVER_RULES_v1.md:46` | R1-R9 are "The response states ... <figure>" (judge.toml l.13-126), 31/57 points |
| B2 | `_COMMON_RULES_v3.md:49` conduct criterion only if the oracle trajectory can show it (JD-7); `LEVER_COMPAT.md:32` "legal only if solve.py really builds and checks that input" | R15 (reordered corpus) and R13 (inspect every file): solve.py only writes and runs the transform (main ~l.555-589), with no shuffle or inspection |
| B3 | `P2_build_v3.md:82` "G3 shares: isolated <= 30%, whole-document on hidden inputs >= 50%, shipped-only <= 5%" | shipped-book checks 69/79 = 87%; hidden (relocated/permuted) 10/79 = 12.7% |
| B4 | `LEVER_RULES_v1.md:37` G2 "No whole-set assert inside a rule-isolating check" | test_output.py:805 `assert set(got) == set(want.cents_by_event)`, :816 `assert rows == want.period_by_event`, :825 `assert rows == want.segment_by_event` |
| B5 | `P2_build_v3.md:82` / `LEVER_RULES_v1.md:41` "G6: at least 2 mutation tests" | 1 mutation (test_output.py:679-692: one currency's curve x1.0375 inside the permuted test); the relocated test (:869) is a copy, not a mutation |
| B6 | `P2_build_v3.md:80` hidden inputs generated verifier-side from a seed with constructed cases | hidden books are only a relocated copy and a shuffled copy of the shipped book (EVAL_SEED l.23); they add no new rule cases |
| B7 | `_COMMON_RULES_v3.md:55` gate "on 2 runs before PL" | pass_summary.json has 1 run on this version; the second run (peer files) was on the pre-QC copy, also under the gate |
| B8 | `P2_build_v3.md:91` "J2 one w3 conduct criterion per lever" | no conduct criterion probes the one lever (strict `amount_minor`); R15 probes reordering, which is not a lever here |

Our gates it meets: tests 30.38 < 100, rubric 90.16 < 100, overall 60.27 < 70 (`_COMMON_RULES_v3.md:55`); 22 tests and 19 criteria are within 35/35 (`:56`); 0 warns; time limit 7200 s >= 3x the oracle's 1.4 s (`:51`); every csv/tsv/jsonl/txt/log has >= 2,031 lines, 31,880 total (`P2_build_v3.md:70`); the instruction is 2,818 chars < 6,000 (`:101`); whole-document grading is stated in instruction.md:38-39 (G5, `:98`). Side note: `KNOWLEDGE.md` is at `master_chat_tasks/knowledge/KNOWLEDGE.md`, not at the path the prompt gave, and its `:45` "test < 90, rubric < 90, combined < 30" contradicts `_COMMON_RULES_v3.md:55`.

## Phase 3: scores, re-graded
1. Recompute: reward.toml weights give 24 x 0.5/79 + 55 x 0.5/61 = 0.1519 + 0.4508 = **0.6027**. That equals `reward_raw.json` 0.6027, `reward.json` 60.27, the `result.json` verifier_result reward 0.6027 and `pass_summary.json` (60.27 / 30.38 / 90.16). The scale differs (raw against x100), but the values agree. The only real mismatch is the judge denominator: 61 at run time against 57 delivered (re-weighted 59.93).
2. Loss table: `loss_table.md` (22 tests, 19 criteria; 0 negatives fired).
3. Re-grade in my verifier image, calling every `_check_*` through `_guard` (driver in `regrade.txt`):
   - Agent's own `run_1/artifacts/app/out`: **24/79 = 30.38 %**, pass/fail identical per test to ctrf.json -> matches.
   - Oracle `bash /solution/solve.sh`: 1.41 s wall, **79/79 = 100 %**, no negative fired.
   - Nop (empty /app/out): **0/79 = 0 %**.

## Phase 4: where Opus lost

### 4.1 Timeline (48 steps; `trajectory_usage.json`: in 2,614,279 tokens (2,499,533 cached), out 70,197, $3.72; agent run 06:42:01 -> 06:57:28Z = 15m27s of 7,200 s)
- #3 `ls` /app, /app/data, /app/out -> **#4 `cat /app/data/schema.md`** (the whole contract) -> #5 policy.ini, fiscal_calendar.json, heads and line counts of 9 files -> #6-#10 legacy, corrections, sales, refunds censuses -> **#11 adjustments census** (prints `badamt` over non-int `amount_minor`) -> #12-#23 legacy, regions, counterparties (348 duplicate ids), inventory, timestamps, fx (NOK starts late), corrections, price parsing.
- #24 first `create /app/out/transform.py` (failed: no dir), #25 mkdir, **#26 06:50:50 transform.py written** (first output, about 8.7 min in, coercion branch already present), #27 first run (closing carry_forward 397).
- Self-testing, #28-#47: region tops, data_quality, opening balances, day shift, skip-reason census (#33), corrections census (#34), normalized sanity, spot greps, empty region_west (#37), interlocks (#39), half-cent (#40), lookup misses (#41), a determinism re-run into /tmp/run2 (#42), a **trimmed** mini-corpus (#43), BOM check, py_compile, and a final clean re-run (#47). #48 finish message.
- It never touched `/tests`, `/logs/verifier` or `solution/` (no such path in any command). It never edited the `amount_minor` logic after #26.
- Export artefact: steps 3, 5, 7, 9, 11, 13, 17, 20 and 29 have no `observation`, because the first call of each parallel pair lost its output. The judge therefore read an incomplete trajectory. It cost nothing here, since R13 still passed.

### 4.2 Every loss
| loss | what the agent did (step) | right answer and the line that settles it | class |
|---|---|---|---|
| 11 tests, 55 pts (rows 6-14, 18, 19 of loss_table) | #26 transform.py:504-514: `if isinstance(minor, str): if not INT_RE.match(minor.strip()): skip; minor = int(minor.strip())` accepts 40 quoted integers -> 10,998 events against 10,958 | reject them: schema.md:34-35 "`amount_minor` must be a JSON integer and carries its own sign"; schema.md:148-149 malformed list "...an `amount_minor` that is not a JSON integer..."; "A malformed event is skipped, is counted against its own event file, and appears in nothing else." | AMPLIFICATION (root GENUINE) |
| R3, 3 pts | #47/#48 reports 397 carry-forward events | 395 (judge.toml R3); patched transform prints 395 | AMPLIFICATION (same M1) |
| R15, 3 pts | #42 re-runs the same corpus; #43 a trimmed subset corpus; never a reordered copy | no line requires it. instruction.md:15 only says "settles a directory it has never seen"; schema.md:10-12 "Row order in an input file is never significant..." states the property but asks for no check | CONDUCT (unstated; also fails JD-7, since the oracle never does it) |

No JUDGE ERROR: both NO verdicts in score.json match the trajectory (397 is in #47/#48; #43 is a trimmed corpus). No ARTEFACT: exception_info is null and the verifier finished in 56 s.

### 4.3 Distinct mistakes
| mistake | test pts | judge pts (run weights) | tests touched | proof |
|---|---|---|---|---|
| M1 coerce quoted-string `amount_minor` | 55 | 3 (R3) | 11 | patched copy -> 79/79 and closing 395 (`regrade.txt`) |
| M2 no reordered-corpus self-check | 0 | 3 (R15) | 0 | judge-only; not patchable in outputs |

M1 alone costs 0.3727 of combined reward; fixing it gives about 0.5 x 79/79 + 0.5 x 58/61 = 0.975.

### 4.4 Did it read the saving line?
Yes, twice. In step 4 (`cat /app/data/schema.md`) the observation holds the full contract, including schema.md:34 and :148-149. Step 11 ran a census that lists every non-int `amount_minor` (`if not isinstance(v,int) or isinstance(v,bool): amt[repr(v)]+=1`). The exported step 11 lost its observation, so I re-ran the exact command on the shipped data (`$S/work/step11.sh`). It prints `badamt Counter({'True': 18, "'-104527'": 1, '115261.0': 1, ...})`, which includes the quoted strings. The agent then rejected bools and floats correctly but chose to "repair" the strings. Its finish message (#48) still claims "non-integer `amount_minor` ... land in the skipped tallies", which is false for strings. R18 did not fire, because R18 grades closing figures and not this claim.

## Phase 5: design anatomy
1. **Instruction**: 49 lines, 422 words, 2,818 chars. Its paragraphs are a story and the authority (l.1-11: "the contract is the authority on every rule", "Deciding which file feeds which figure is part of the work"), the deliverable CLI (l.13-19), constraints (l.21-24), the 14 artifact paths (l.26-36), exactness and interlock warnings (l.38-42), the closing message (l.44-46) and the timeout (l.48-49). It states no rules itself: every rule is delegated to schema.md (297 lines; sections at :22 events, :54 reference files, :105 policy.ini, :113 settling, :143 malformed, :154 orphan links, :170 ladder, :194 record, :210 serialization, :230 aggregates, :275 closing report). It deliberately leaves out any hint of which malformations exist, any worked figure, and any self-check advice.
2. **Data**: 13 files plus schema.md, 31,880 lines, about 2.2 MB: csv (sales, channels, counterparties, fx_rates, inventory, product_catalog, regions), tsv (refunds), jsonl (adjustments), Latin-1 pipe text (legacy.txt), log (corrections.log), ini (policy, 23 lines), json (fiscal_calendar). No xlsx/pdf/parquet/sqlite, no decoy files, no next-period tier. Where the traps sit: adjustments.jsonl `amount_minor` has 40 quoted ints (the lever), 18 bools and about 34 integral floats (the last two are easy rejects that build false confidence); kind case variants (CREDIT/Fee) are legal and `writeoff` is illegal; counterparties hold 348 duplicate ids (latest updated_at, then seat); inventory has Z901-Z903 depots not in regions; fx has NOK starting late (carry-forward/predated drop); timestamps include impossible days; corrections.log has winner-per-field. Opus handled every trap except the string ints.
3. **Tests**: 22 checks (19 positive: 4 x 1 + 15 x 5 = 79; 3 negatives -5/-3/-3). The verifier rebuilds the shipped book from an embedded zlib/base64 blob (test_output.py:79-98), so edits to /app/data do not count. It recomputes everything with an independent reference `_Ledger` (:172-280) and compares whole documents, type-strictly (`_same`, :611). It re-runs the agent's transform on a relocated copy (:869) and on a shuffled copy with one currency curve x1.0375 (:679-692, :877; it also asserts the total moved), under `setpriv` nobody with a 600 s cap per run (:619-648). The negatives are memorised book (:890), AST network/process/shell (:936) and double-run nondeterminism, capped at 240 s (:948). The verifier timeout is 2,700 s. Concept spread: the event-acceptance set reaches 11 tests (8 document tests plus 3 rule tests with whole-set asserts at :805, :816, :825). Shares: shipped-book 69/79 (87%), hidden copies 10/79 (12.7%), rule tests checked on subsets (5, 15, 16, 17) 20/79.
4. **Judge**: 19 criteria, batched. Positives total 57 (delivered) / 61 (run): R1-R9 closing figures (31 pts, user-facing message), R16 artifact paths (message, 3), R10-R15 and R19 process/code (trajectory, 23). Negatives R17 -3 (repeated error) and R18 -5 (figure contradicts own run). The oracle's behaviour (`bash solve.sh`, which writes and runs the embedded transform and prints figures and paths) meets R1-R9, R11, R16 and arguably R10/R12/R19 (via the code). It cannot show **R13** (it inspects no file) or **R15** (no reordered corpus), and **R14** is borderline (it runs via runpy inside solve.py, not as a CLI call). That is a JD-7 gap the kit did not flag.
5. **Solution**: solve.sh 1 line; solve.py 589 lines / 23.8 KB, which embeds the transform as a string, writes /app/out/transform.py and executes it (l.555-589). Stdlib only, 1.41 s wall. It shares 4.3% of its lines with the verifier (QC report l.62).
6. **Robustness**: 55 of 79 test points (70%) ride on the single yes/no decision "accept quoted-integer `amount_minor`". 2 of 2 observed Opus runs (this one, and the older run in the peer files) said yes through different code (INT_RE coercion against `json.loads(value.strip())`), and both scored tests 30.38. Judge spread ±3 (R15) ±3 (R3 tied to M1). Expected spread: combined about 60-63 while Opus keeps coercing; if a run reads schema.md:34 strictly, it jumps to about 95-98. The distribution is bimodal, not ±5. One more run would most likely land at 60 ± 3 (UNVERIFIED beyond n=2).

## Phase 6: what we take from it

| design choice | evidence (file:line, points) | kit check that allows it | our v3 templates | adopt / adapt / avoid |
|---|---|---|---|---|
| L5 strict type rule stated twice as a bare property (field block plus malformed list), separating rows shipped, with easier malformations (bools, floats) beside it | schema.md:34-35, :148-149; 40/2653 rows; M1 = 55 test + 3 judge pts, 2/2 runs | LEVER_COMPAT.md:19 L5 CONDITIONAL (IN-16, TS-17, DS-4, CL-3, CL-5) | allowed: LEVER_RULES_v1.md:17 L5, :30 W5 | **adopt** (add the easy-reject decoys) |
| Instruction delegates every rule to one contract file and states exactness and interlock up front | instruction.md:6-11, :38-42; no IN finding | IN-15/IN-16 pass; CL-4 exemption ("instruction states only an exact match counts") | P2_build_v3.md:98 G5 | **adopt** wording |
| Whole-document exact grading on the shipped book, type-strict `_same` | test_output.py:611; 8 doc tests x 5 = 40 pts lost to M1 | TS-26/JD-14 allow cascade (LEVER_COMPAT.md:30); CL-4 exempt via G5 | conflicts with P2_build_v3.md:82 G3 (shipped-only <= 5%) | **adapt** (allow it when relocate + permute re-runs and a memorised-book negative exist) |
| Whole-set assert inside per-rule tests | test_output.py:805, :816, :825; 15 pts of the 55 | TS-13 minor not fired; TS-26 not fired | forbidden by LEVER_RULES_v1.md:37 G2 | **avoid** (double bills; makes the score one-decision bimodal) |
| Verifier rebuilds the shipped book from an embedded blob and re-runs the agent's program on a relocated and a permuted + rate-scaled copy | test_output.py:79-98, :679-692, :869, :877; 10 pts; neutralises /app/data edits and hardcoding | TS-24 isolation, CL-2 forgery price (QC report l.81: forgery 4/79) | partly: P2_build_v3.md:80-82 G6 | **adopt** as a G6 mutation pattern |
| AST network/process negative plus double-run nondeterminism negative | test_output.py:936, :948 | TS-16, TS-27 (fixed in QC) | P2_build_v3.md:85 G4 | **adopt** |
| "States figure X" judge criteria R1-R9 (31/57) | judge.toml l.13-126; gave back 28/31 pts, holding the rubric at 90 | JD-15/CL-2 accepted once figures were added (QC l.31) | forbidden by _COMMON_RULES_v3.md:48 J1 | **avoid** (inflates the rubric; double-bills M1 via R3) |
| Unstated conduct criterion the oracle cannot show (R15 reorder; R13 inspect all) | judge.toml R15 l.195-204; solve.py main l.555-589; 3 pts lost | JD-7 should fail; the kit missed it | _COMMON_RULES_v3.md:49, LEVER_COMPAT.md:32 | **avoid** |
| setpriv nobody, 600 s per-run cap, assert no writes outside the out dir | test_output.py:619-648 | TS-9, TS-24 | not stated in P2_build_v3 | **adopt** |

### Template / playbook edits (proposals only; none made)
1. `knowledge/LEVER_RULES_v1.md:17` (L5 row): add "pair the separating rows with 1-2 easier malformations of the same field (bools, integral floats) that the reflex rejects, so the solver feels it handled the type rule; state the rule twice (field block plus malformed list)". Evidence: Phase 6 row 1, 2/2 runs, 55 pts.
2. `prompts/templates/P2_build_v3.md:82` (G3): add an exception: "shipped-only share may exceed 5% when every program test is also re-run on a relocated and a permuted copy and a memorised-book negative exists". Evidence: row 3 (87% shipped, 0 QC findings, forgery 4/79).
3. `prompts/templates/P2_build_v3.md:82` (G6): name this mutation pattern: "shuffle every event/reference file and scale one governed curve by a non-round factor; assert the dependent total moved". Evidence: row 5, test_output.py:679-692, :877-881.
4. `prompts/templates/P2_build_v3.md:91` (J2): add "solve.py must perform the conduct act itself (construct the input and print the check), or drop the criterion. Peer evidence: R15 passed QC while the oracle cannot show it". Evidence: row 8, B2.
5. `prompts/templates/P2_build_v3.md:98` (G5 example): add instruction.md:38-42's two-sentence form ("An artifact counts only when every single value in it is exact ... the figures interlock ...") as a model that also explains the cascade without naming a lever. Evidence: row 2.
6. `knowledge/KNOWLEDGE.md:45`: replace the old per-run gate "test < 90, rubric < 90, combined < 30" with `_COMMON_RULES_v3.md:55` "tests < 100, rubric < 100, overall < 70, on 2 runs". Evidence: the B7 side note (the two files contradict each other).

### Peer mining (G4/A and G4/B, older copy, older run)
- **Agree**: one root cause (40 string `amount_minor`), GENUINE, 11 x 5 = 55 by amplification; the whole-set asserts in the per-rule tests are a design quirk (A) / RISKY under TS-13/TS-26/TS-20 (B); R15 is unstated conduct (A, B: breaks JD-15); the lever is L5 strict beside normalise, with the trim rule (schema.md:14-16) pulling the other way (B); 87% shipped-only (B).
- **New evidence**: the delivered run is a second, independent Opus attempt that made the same decision through different code (`INT_RE` coercion against the older `json.loads(value.strip())`). The lever reproduces, and the tests scored 30.38 both times.
- **Disagree**: A and B say "JD-7: the oracle meets them" (R15). solve.py never reorders or inspects anything, so the oracle cannot show R15 or R13 (B2). Also, the peer files predate the CL-2/JD-15 fix: R1-R9 now carry exact figures and do grade correctness. That is why R3 failed in this run (397), where the older run passed every figure criterion.

## UNVERIFIED
- A third Opus run's score (the spread estimate rests on n=2).
- Whether the judge would pass R10/R12/R14/R19 on an oracle trajectory (no oracle trajectory exists; the claim comes from reading solve.py).
