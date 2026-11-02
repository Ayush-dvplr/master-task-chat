# C_0b27b9dc (Security) — card

Task folder `T=/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Final_Delivery/0b27b9dc-7985-54f1-a120-46e6810315a3`; run `R=T/trajectories/claude-opus-5/run_1`.

## 1. Scores and verdict
- Recorded 61.39 / 96.47 / 26.32 (final = mean of halves; reward.toml 0.5/85 tests, 0.5/57 judge).
- Step 1 verdict: tests GENUINE, judge PARTLY (see A_0b27b9dc.md).
- Genuine test points lost: 3/85 (`test_cost_control_names_a_set`). Negatives: 0 fired.
- Judge: 42 of 57 lost = 13 failed probes x3 (39, genuine in the sense the agent did not show them, but nothing in the instruction asked for them) + R6 -3 fired (ARTEFACT: the file it flags is the deliverable `lgactl.py`). Without the artefact the rubric is 31.58 and the final 64.02.

## 2. Inventory
- Domain: Linux grant admission (SELinux type transitions, PAM stack walk, capability sets, seccomp filter decisions, cost-bounded least-privilege grant plan). Archetype: domain-calculation + format-recovery (multi-encoding corpus) with a computational core (fixed-point grant plan with a minimality witness).
- Files the agent sees: ~60 under /app/data: SPEC-LGA.md (39 KB, 6120 words) + six appendix md (705-1004 words each; total md 13,732 words); the same record families delivered in 5 variants a-e across jsonl, csv, tsv, psv, ssv, logfmt, rfc5424 syslog, toml, ini, s-expression, fixed-width, properties; cost-controls-a.csv / -b.jsonl.
- Instruction: 2422 words (instruction.md 14 KB).
- Tests: 34 rewardkit criteria (29 positive = 85; 5 negatives = -23). Judge: 33 binary criteria (positive 57), batched, gpt-5.6-sol, trajectory via ATIF.
- Reward split 50/50 of normalised halves. Agent timeout per task.toml (not material; agent finished in 17.7 min, $6.12).

## 3. Core difficulty
A correct solver must decode ~a dozen carriers, canonicalise identifiers, walk four policy engines and then run a fixed-point grant plan whose cost model is defined by "controls" over atoms. The single loss is a definitional word: a control's `atoms` field "names a set" (SPEC-LGA.md:134-136, :422), so a repeated atom in two spellings (producer form and canonical form) counts once. Class: **implied by a definition** (ordinary-word meaning fixed by the spec — the instruction warns "including where it fixes the meaning of an ordinary word"). Why a blind Opus does not transliterate it: the shipped corpus has no duplicate, so the agent's list-based reading is right on every shipped and unseen plain corpus; only a test-time **variant** of the unseen corpus plants the duplicate. The 2400-word contract plus 13.7k words of spec are not a spec Opus can mis-transliterate cheaply; it did transliterate 82/85 in 11 minutes to first program, so the core itself is NOT what held it — the judge was.

## 4. Test architecture
- Expected values: computed at test time by an embedded reference solver (`_REF_SRC`) and an embedded seeded corpus generator inside test_output.py (211 KB). `__main__` reproduces the shipped corpus bytes (:4980-4985). Seeds SAMPLE_SEED=20260914, EVAL_SEED=5231180497 (:3707-3708).
- `check_artifact` (:4275-4287): each of 24 artifact tests asserts BOTH the delivered artifact on the shipped corpus AND the solver's rebuild on the unseen EVAL corpus ("the plan and the solver stand or fall together"). stacking_check labels these `shipped_only` — WRONG: every artifact point (70/85) needs the hidden corpus right. Effective hidden share ≈ 100% of artifact weight.
- Variant tier (:4386-4457): `VARIANT_BUILDERS` (encodings, audit, controls) mutate the EVAL corpus to add one feature; `check_variant` grades only artifacts the solver already got right on the plain unseen corpus and requires at least one "moved" artifact to be right — so a variant check isolates exactly one rule and does not re-charge upstream errors (comment at :4411ff). This is a **per-rule isolated mutation tier on top of whole-document grading** — NEW relative to TD6 (our mutation tier re-grades whole reports).
- `test_regenerates_on_reduced_corpus` (reduce=True, :4592-4599); determinism run_tag "again" (:4652); `test_contract_and_exit_codes` (exit 0/2/3).
- Negatives use polarity inversion (docstring "Negative tests use polarity inversion"); 5 acts each -5/-3: hardcoded sample answers, embedded shipped corpus path, output depends on more than content (order/name), writes undeclared files, imports outside contract. None fired.
- Assertion messages present (`_first_difference` gives line N delivered vs required) — G7 satisfied.

## 5. Lever table (failed checks)
| id | w | rule | locations | sentence form | agent's reading | correct reading | why self-test missed | fully stated? | nearest |
|---|---|---|---|---|---|---|---|---|---|
| test_cost_control_names_a_set | 3 | a control's atom list is a set after canonicalisation; total = sum over distinct atoms | SPEC-LGA.md:134-136 "`atoms` names a set of atom identifiers, written as a vertical bar separated list"; SPEC:36-39 canonical identifier form; SPEC:422 "A control names a set of atoms and gives in `total` the sum of their effective costs" | implied by a definition (the word "set") + canonicalisation stated elsewhere | agent lgactl.py:823-831 `ids = [cid(x) for x in ... .split("|")]` keeps a list, so a repeat is counted twice | dedupe after canonicalising | shipped data holds no repeated atom; the agent's step-27 multiplier probe looked at pairs, not repeats | YES (stated; separating case hidden-only) | L6 scope via glossary definition / R7 overloaded term (KNOWN); the delivery mechanism (variant built from the hidden corpus, graded only where the plain run is right) is NEW |

## 6. Judge architecture and losses (main section)
Structure (judge.toml, TRUTH.md:242-248): 33 binary criteria, three bands.
- **Band A, rules of engagement + final-reply facts (R1-R4, R7-R10, all w1, final_answer or trajectory)**: names the 25 deliverables; stdlib/offline; invokes the solver with two args; closing figures by name; four exact closing figures. All PASSED (8 pts).
- **Band B, negatives (R5 -5, R6 -3, R11-R16 -3/-5)**: edits /app/data; hand-creates a file in /app/out; reports an uncomputed reconciliation; uses an unopened field/constant; repeats a failing command 5x; spoken count disagrees with an artifact ("other than" wording); false must-admit claim; ruled-out atoms never measured. Only R6 fired (artefact, below).
- **Band C, sixteen verification probes (R18-R33), w3 each = 48 of 57 positive points (84%), trajectory, critically_important**. Template: "The agent runs its solver or its <reader> on an input, shipped or constructed, that <edge feature> and shows <the decision>" / "checks one <instance> … and shows the <rule> its solver named" / "recomputes … with a calculation separate from lgactl.py and compares". TRUTH:242-248: "none of its observables is a file a test compares".
- R17 (state_change w1) one shared replay function — PASSED.

Failed criteria (13 positives x3 + R6):
| R | edge it wanted shown | what the agent did | class |
|---|---|---|---|
| R18 | relabel stream, last-wins | built relabel handling, never displayed one relabel instance (judge: "aggregate count only") | process step (probe) |
| R19 | note running to end of record | no instance shown | probe |
| R20 | rfc5424 record with a second SD element | parsed all carriers (steps 13-18), never showed one | probe |
| R21 | PAM first-wins return | step 36 ledger counts only | probe |
| R22 | uid gate boundary equality | not shown | probe |
| R23 | PAM deciding module named | not shown | probe |
| R24 | seccomp filter tie | not shown | probe |
| R25 | errno required vs optional | not shown | probe |
| R26 | nnp effective set recomputed separately | not shown | probe (independent recompute) |
| R29 | replay one minimality witness separately | step 44 counted witness rows, no replay (judge: "counts witness rows but does not independently replay") | probe (independent recompute) |
| R30 | advisory capability | not shown | probe |
| R32 | nonzero arg_index | not shown | probe |
| R33 | undeclared filter default action | not shown | probe |
| R6 (-3) | "creates a file in /app/out by hand, outside any run of the solver, and leaves it beside the twenty five deliverables" | step 46 `cp /tmp/lgactl.py /app/out/lgactl.py` then ran it from there; lgactl.py IS deliverable 25 (R1 counts it; oracle solve.sh comment "lgactl delivers itself as /app/out/lgactl.py") | ARTEFACT (judge over-read) |
Passed probes: R27 transition rank (steps 15, 36), R28 closing-figure crosscheck (step 50), R31 cost multipliers shown (step 27).

Why QC accepted the probe band:
- JD-15 conduct branch, step 2: "an odds-raising approach weighted 1 or 3 passes" (04_Judge_QC.md:92). Checking a constructed edge case raises the odds; w3 keeps them under the minor threshold (w5 would be a minor).
- JD-8: the probe reads the transcript, not an artifact (TRUTH:242-248 states this explicitly) — distinct observable, so no overlap even though every probe mirrors a tested rule. Our J8 ("no criterion restating a tested method") would have refused these; the kit does not.
- JD-7: the oracle (solve.sh/solve.py) prints nothing — it cannot satisfy any probe. No QC report exists to show whether this was raised; the bundle shipped with it (KNOWN K8 "JD-7 oracle-unsatisfiable shipped").
- JD-5: each probe is one edge, one observable ("shows one …").
Why a strong agent loses them without unfairness: the instruction never asks it to show edge instances (grep for show/probe/verify = only "demonstrate" for minimality, instruction:100-107). Opus self-tests by aggregates (conservation, counts, determinism, md5 of data) — it never prints a single worked instance per rule. Each probe is a separate w3 so the score scales with how many edges it happened to display (3 of 16).
Shape that costs points fairly: **"shows one instance of <edge> and the decision its program made for it"**, one per trap rule, w3, trajectory, many of them (16), dominating the positive total.

## 7. How it passes QC (no QC report found)
- IN-15 (negatives trace to sentences): R5 ↔ instruction:223 "Leave `/app/data` exactly as you found it"; R6 ↔ instruction:223-228 "Write nothing into /app/out beyond the twenty-five files named above, so no scratch file"; test negatives (undeclared files, imports) ↔ :213-216 stdlib-only, :38 "exactly these, at exactly these paths".
- IN-16 / IN-17: rule stated in SPEC (governing file, W2); instruction announces THAT ordinary words are fixed ("including where it fixes the meaning of an ordinary word") without saying which (W1, LV1).
- TS-13: each artifact test asserts two corpora in one criterion (shipped + unseen) — an and-bundle over corpora, not over rules; QC kit treats this as one observable (the artifact). KNOWN K7.
- TS-16/TS-19: the variant check stays inside the spec (a duplicate atom is a legal input to "a set"), so not stricter-than-contract.
- TS-20: core never weight 1 — artifact tests 3/5.
- TS-26: no duplicate observables (variant checks only grade where plain is right).
- AL-1: every graded rule has a SPEC line; the 0b determinate test holds.
- AL-28: negative per act ≤ -5 across layers: R5 (-5 judge) and the test negatives target different acts (data edit vs undeclared outputs).
- CL-4/CL-5: exactness via "same bytes", UTF-8 no BOM (:151), byte-exact manifest (:198-199).
- JD-7: oracle cannot show probes — passed anyway (risk our QC_RULINGS marks FAIL: district-heat v1:363).
- JD-11: negatives are task-specific (uncomputed reconciliation, unopened constant, ruled-out atoms).
- JD-15: probes = conduct, odds-raising, w3 → pass.

## 8. Leak avoidance
- "The specification is authoritative and complete. It states every definition, every constant, every boundary…" (W2/W10 — instruction points at one governing doc).
- "including where it fixes the meaning of an ordinary word" (W1 — says THAT, not WHICH; LV1).
- "Nothing here tells you how many files there are, what any one of them holds, or which encoding it uses. Working that out is part of the task." (W8 — odd carriers, no listing).
- Minimality "is a property you have to demonstrate rather than assert" — announces a coupling, not the trap (LV7).
- Shipped data does NOT separate the readings for the "set" rule (W5 — hidden only); no worked example (W6); no visible expected outputs (W11, LV3).
- LEAK_LIBRARY row it avoids: "explicit sentence naming exception" (the word "set" is a definition, not an exception sentence) and "shipped boundary rows" (no duplicates shipped).

## 9. Agent behaviour
- Reads: SPEC (steps 5-7, three chunks), all appendices (8-12) by minute 0.6; multi-format dumps 13-18; helper reader at step 19 (min 3.7); probing 20-29; **first full program step 30 at 10:20:46 (~11 min)**; first run step 33 (min 12); inspections 34-39; determinism/shuffle 42; exit codes 43; deliver step 46; data md5 unchanged 48; closing figure crosscheck 50; final 51 (17.7 min, $6.12).
- Graded logic changed after first program only in small edits (31-32, 40-41, 45).
- Self-tests: determinism, order-invariance (shuffle), exit codes, conservation closure, md5 of /app/data, closing-figure recompute. All aggregate; none constructs an edge input. Covered levers: determinism, ordering; not the "set" rule.
- Final claim vs reality: claims all 25 deliverables correct and stdlib-only — tests 96.47 agree; it does not claim any probe.

## 10. Passed checks and criteria
- 24/24 artifacts on shipped + unseen corpus, reduced corpus, encodings variant, audit variant, exit codes: easy because the spec is complete and self-consistent and Opus transliterates a well-specified multi-format spec reliably.
- Judge band A (final reply facts, rules of engagement) and 3 probes it happened to perform.

## 11. Take-aways
- ADOPT (SAFE, NEW): **variant tier graded only where the plain hidden run is already right** — isolates one rule per check, no cascade double-charge; build: mutate the hidden-seed corpus by one feature at test time.
- ADOPT (SAFE, KNOWN-ish → NEW scale): **probe band** — one w3 trajectory criterion per trap rule, "runs its program on an input, shipped or constructed, that <edge> and shows <decision>", 10-16 of them making ≥80% of judge positives. Passes JD-15 as odds-raising conduct at w3. A transliterating agent that self-tests by aggregates loses most of them.
- ADOPT (SAFE, KNOWN): every artifact test asserts shipped AND unseen corpus in one criterion.
- AVOID (RISKY): negative "hand-creates a file in out/" when the program itself is a deliverable in out/ — judge fired it on the delivery copy (artefact -3). Word negatives to exclude the program file explicitly.
- RISKY: oracle cannot satisfy any probe (JD-7); our QC_RULINGS fail this. If adopted, the oracle trajectory must not be the yardstick or we need a stated reading of JD-7 for conduct probes.
