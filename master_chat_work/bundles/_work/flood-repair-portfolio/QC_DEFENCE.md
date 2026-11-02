# QC_DEFENCE ed7b0c2 flood-repair-portfolio

Live rule text quoted from checks.json (qc_reverse/A). Fallbacks are QC_FIX_PLAYBOOK_v2 rows; none of
them softens a lever.

## LV-FP-1 exact optimum
| rule | live text (quoted) | why it passes | fallback (playbook row: DO) |
|---|---|---|---|
| IN-15 | "A rule that is graded but appears in no file the agent can read costs the honest agent reward" | objective, tie-break, limits and stdlib-only all in contract.md "Portfolio"/"Limits"; QC_RULINGS IN-15 cohort v2:119 PASS (stdlib, no network stated) | IN-15: add the missing sentence to contract.md, never to instruction.md |
| IN-16 | "A finding without both readings written out is not usable" | tie-break sentence has one reading (position by position, smaller id); benefits >= 1 so no prefix case | IN-16: rewrite the one sentence in contract.md with the comparison spelled out |
| IN-17 | no sentence announces what input establishes | contract states rules, never "the data shows" | IN-17: delete the announcing clause |
| AL-1 | "Everything graded is promised." | instruction promises fresh books in the same format, graded whole, exact match only | AL-1: add the promise sentence to instruction.md |
| AL-27 | "a rule only counts as graded when the test's input actually constructs the situation" | planted equal-total small rounds in shipped and every hidden book; large rounds in every book | AL-27: generator asserts the fixture, add the missing plant |
| CL-4 | "Partial credit tracks partial correctness." | REBUT with FC:491 "An instruction that states out loud that only an exact match counts has set that bar deliberately"; feasibility tested apart from optimality; one-fact-wrong score in COST_TABLE.md | CL-4: partition hidden checks by document family (already), never relax exactness |
| TS-13 | "A test asserting two unrelated properties hides which one failed" | one whole document per view = one property (QC_RULINGS TS-13 PASS) | TS-13: split along document lines |
| TS-19 | "every promise made to the agent must be graded by something" plus district-heat v1:312 FAIL (hidden outside stated bounds) | generator asserts every hidden round within stated limits | TS-19: tighten generator asserts, never widen the contract silently |
| TS-20 | "a core-deliverable test carrying weight 1, or an existence/formatting check carrying 5, is wrong" | selected lists and summary 5, documents 3, existence 1 | TS-20: reweight to 5/3/1 |
| TS-26 | "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice." | feasible (true conflicts), selected (lists only) and summary (whole doc) use different logic; QC_RULINGS TS-26 PASS district-heat v3:185 | TS-26/JD-14: merge selected-lists into summary whole-doc and move its weight there |
| AL-28 | "name the single concrete agent action that triggers it" | current owners: tests -3 for shipped-answer substitution on H1; judge R14 -5 for unrun-check claims, R15 -5 for false rejection claims, R16 -5 for executed verifier access | AL-28: one negative per concrete act; comments are never proof |
| JD-7 | "Every criterion must be satisfied ... by the shipped oracle" | solve.sh self-check prints `check <id> ok` per conduct criterion | JD-7: add the self-check stage line |
| JD-15 | what a criterion may require | conduct only, no figure criteria, no absence positives | JD-15/16: relabel or drop the figure criterion |

## LV-FP-2 conflict derivation
IN-15 (all three sources and the site-name rule in contract.md "Conflicts"), IN-16 (withdrawn is the only
non-counting status; shared never conflicts; site id stands for every proposal of that round at that
site: one reading each), IN-17, AL-1, AL-27 (each source covers >= 20% of large-round edges; decoys
planted in shipped and hidden), TS-13, TS-26 (feasible check reads conflicts, dq reads conflict_pairs:
different observables). Fallback: IN-16 row, rewrite the single sentence; AL-27 row, add the plant.

## LV-FP-3 valuation
IN-15 (formula and every lookup named by field in contract.md "Benefit"), IN-16 (premium "added to every
proposal at that site"; override "when that field is not empty"), W4 (override names its field), AL-27
(overrides, shared sites, negative uplift planted everywhere), DS-25 (every key of the VALUE row written
in contract.md). Fallback: IN-16 row; DS-25 add the literal.

## LV-FP-4 fault precedence (secondary)
IN-15/IN-16 (fault table per file plus the order sentence), AL-27 (two-fault rounds, reordered hidden
manifest), TS-19 (only listed faults generated), DS-25 (all five codes and `ERROR MISSING_FILE <file
name>` in contract.md), TS-20 (dq checks weight 3). Weight share 12/108 = 11% (<= 25%). Fallback: AL-27
add plant; IN-16 rewrite.

## Cascade (COUPLING G1)
"Every reported figure of a round is computed from the one portfolio chosen for it." A wrong portfolio
fails summary, policy, region and segment documents of the same book. Rules: CL-4 (REBUT, FC:491 plus
"one test legitimately owning most of the reward ... is good design"), TS-26 (each document is a
different observable; district-heat v3:185 PASS), AL-28 (cascade is positive checks failing, never
stacked penalties). Fallback: CL-4 row, partition by document family; never drop exactness.

## Other gates touched
DS-4 (no answer in environment/: no optimum, list, total; random id tokens), DS-24 (solve.py vs
test_output.py overlap < 20%), DS-27 (TRUTH narration; OPEN CONFLICT Q18 if VB 15.5 disagrees), JD-12
(8 to 35 criteria, sum of negatives <= sum of positives), TS-23 (34 checks, under 35).
tests_qc B4 (a tests/*.py naming /logs/verifier) was hit once and fixed by narrowing the negative to
/tests; validator 7.4 requires `negative_hardcoded_sample_answers` with negative weight: added at -3
(G4 cheat act now requires shipped-answer substitution in hidden output), never fires on correct hidden output.

## P12 fix v1 7cc7c61 (31 Oct) additions
| rule | design | why it passes now | fallback (playbook row: DO) |
|---|---|---|---|
| AL-27 (contract.md:21 "a data row is any later non-empty line") | H1, H2, H3 carry one empty line after data row 50 of `proposals.csv` and `permits.csv` (hidden_meta.json `blank_row` 50, bookgen.py `_assemble`); faulty rows follow it in every hidden book, so a reader that counts the empty line or stops at it reports wrong rows or misses rounds | 05_Alignment_Integrity_QC.md:38 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters"; RULE_COVERAGE row with mutants blank_line_counts_as_row and blank_line_ends_file | AL-27: move the empty line ahead of more faulty rows; never add it to the shipped book or delete the rule |
| JD-7 R8 | solve.sh self-check times a fresh run on /app/data and compares it with 20 s (`check R8 ok (... s for the shipped book)`) | 04_Judge_QC.md:76 "Every criterion must be satisfied ... by the shipped oracle" | JD-7: fix the oracle, never loosen R8 |
| TS-11 | each hidden book run has a 20 s wall limit (contract.md:15); a time-out loses that book's checks | KEEP: Ayush exception 31 Oct 11:45 (flood-only, losses by time-out may be the whole lever); 03_Tests_QC.md:41 asks bounds be stated, contract.md:15 states it | TS-11: none needed; if forced, raise BOOK_SECONDS in tests and contract together, never drop the limit |
| Oracle x3 | three oracle runs, not five | Ayush acknowledgement (KEPT row); Final_checklist.md:390 | run five if QC insists |

## Harden r2 cb8dada (1 Nov) additions
Change: H1, H2, H3 regenerated from the same generator with new seeds 815301, 822402, 833503 and the large-round list of each book repeated 30 times (60 large rounds plus 40 small per book, 100 rounds), registers scaled with k = 60 (hidden_meta.json, test_output.py:670 `_BOOKS`); `_launch` (test_output.py:1163) runs the program in its own session and `_stop_untrusted` (test_output.py:1183) kills its whole process group and every leftover process of user nobody after the run. Every other check body is byte-identical (WORK/h2_a1/digest_checks2.py: b1d31eb43bec1684 before and after). No doc, judge, shipped data, weight or registration changed. Previous QC copy for the recheck: QC/copies/6a62b99.

| rule | design | why it passes now | fallback (playbook row: DO) |
|---|---|---|---|
| TS-11 / Law-1 v3.5 (time-out lever) | a program slower than 20 s on a hidden book loses that book's seven checks (25 points); each book is its own `delivered()` call (test_output.py:1237), so a time-out never costs a non-lever check | Ayush 31 Oct 11:45, decisions.jsonl:608 verbatim: "(b) Run a full QC, then one paid run with a time-out exception like outage's. Expect about 3 to 4 hours and a coin-flip result." (the original writes the range with a dash); the limit is stated at contract.md:15 "within 20 seconds of wall time"; no shipped input is slow (reference 0.16 to 0.25 s on the shipped book, a1 program 2.2 to 3.3 s at a1 steps 55, 61, 70); reference 1.12 s busy on the largest hidden book = 1/18 of the limit; the time-out cut is a measured gap (a1 program over 60 s on every hidden book, kill2.log), never a margin of 20% or less | raise BOOK_SECONDS and contract.md:15 together, never drop the limit; rep20 books (kill1.log) keep a1 above 2x the limit too |
| TS-11 (cap really stops the program) | `_launch` Popen with `start_new_session=True`, `communicate(timeout=BOOK_SECONDS)`, then `_stop_untrusted` kills the group and every process of uid nobody; `/proc` walked in sorted order | fork probe (WORK/h2_a1/forker/derive_report.py: child python3 busy loop, multiprocessing Pool(2), double-forked sleeper, setsid escapee): before the fix 4 live processes survived the time-out (logs/fork1.log), after it 0 (logs/fork2.log), so no stray worker steals CPU from the next book's run | none needed |
| TS-19 (every hidden size inside the stated limits) | each hidden book has 100 rounds (contract.md:11 allows 200), rounds of at most 160 proposal rows (contract.md:11), conflict records per round inside 900 (contract.md:12), rates, uplifts and premiums inside contract.md:13 | `_check_bounds` (test_output.py:601) asserts every limit when a book is built; WORK/h2_a1/gen300_rep30.py built 300 seeds of each rep30 spec in Docker: 0 assertion errors, 60 large and 100 rounds per book, all 19 fault kinds planted (logs/gen300.log) | drop to rep20 (40 large rounds), never exceed contract.md:11-13 |
| IN-17 | no word about size, speed, density or method added anywhere; instruction.md and contract.md unchanged (diff empty) | the only speed sentence is the pre-existing stated limit contract.md:15; IN-17 forbids announcing a discovery, and nothing new is announced | none needed |
| IN-15 / IN-16 | no rule of engagement added; the time limit is an outcome bound stated once (contract.md:15) with one reading (wall time per book) | unchanged text; the check counts a book as lost only when the run exceeds the stated 20 s | none needed |
| DS-21 | an exact solver inside 20 s is reachable from the agent-visible files: the reference runs 0.95 to 1.12 s busy per hidden book, the careful VE programs 5.9 to 7.9 s (kill2.log) | the structure that makes it fast (local conflicts, small separators) is in every shipped large round (proposals.csv:958, :1312) | none needed |
| TS-23 | 34 checks (32 positive, 2 negative), unchanged | 03_Tests_QC.md:62 warns only above 35 | none needed |
| TS-26 | `reruns_identical` (test_output.py:1332) compares two fresh H1 runs with each other (determinism); the H1 checks compare one run with the expected documents | different observables, same as before the harden; a time-out fails both because no document exists, which is the AL-28 cascade of positive checks, not a double penalty | none needed |
| JD-5 / JD-8 | judge.toml unchanged; no criterion reads hidden-book output | the judge reads the trajectory, tests read hidden documents | none needed |
| AL-2 / AL-27 | promises and fixtures unchanged; the bigger books carry every planted fault kind (gen300 19/19) and the blank_row 50 line | 05_Alignment_Integrity_QC.md:38 trigger depth still met on H1 to H3 | none needed |
| CL-2 | forgery price measured in the gate lane (HARDEN_REPORT.md); hidden books are built fresh, so a forged artifact set earns only artifacts_present and the shipped checks it copies | Final_checklist.md:489 | none needed |
| CL-3 | no asserted hidden value is in any shipped file; hidden books are regenerated at grade time and their expected documents computed by the verifier's own solver (`_portfolio`) | Final_checklist.md:490 | none needed |
| DS-22 | TRUTH.md sizes, timings and sha256 rewritten by script last (WORK/h2_a1/truth_update.py) | TRUTH.md describes the shipped bundle | none needed |

## Harden r4 ea94780 (1 Nov): shared-crew limit (LV-CAP) and time-budget sentence
| rule | design | why it passes now | fallback (playbook row: DO) |
|---|---|---|---|
| IN-16 / DS-21 (new rule sentence) | contract.md:62 whole: "A portfolio of a planned round is a set of its proposals with no two in conflict. A crew whose mode is `shared` can work on at most four of the proposals in a portfolio. Its total benefit is the sum of the benefits of its proposals. The chosen portfolio of the round is the one with the greatest total benefit. When several portfolios share that greatest total, compare their id lists, each sorted in ascending order, at the first position where they differ; the portfolio whose list has the smaller id there is chosen." | one reading: the set of portfolios is the conflict-free sets in which each shared crew appears at most four times; the chosen one is the greatest total over that set, ties by the unchanged id-list order. `mode` and `shared` are defined at contract.md:27 and occur in crews.tsv (946 shared rows, crews.tsv:3 `C7815 shared`). The verifier's own `_capped` (test_output.py:1260) enumerates every allowed four-subset of each over-full shared crew and takes the greatest total then the smaller sorted id list; solve.py threads a count into its frontier search (solve.py:212-296); both agree on 300 seeds + H1-H3, M and the shipped book (h4_rule/proto/crosscheck.py, logs/crosscheck2.log SEEDS_SAME 0 300). Each planted round has a unique capped optimum (generator asserts strict top, test_output.py:656) | IN-16: spell the limit as "no portfolio holds five or more proposals of one shared crew" in the same sentence |
| IN-15 | the limit is in the one rule file next to the portfolio definition (W10); no other file defines a portfolio (grep portfolio/conflict/shared/mode, HARDEN_REPORT) | contract.md:3 and :64/:70/:72/:76 only use the word; :52-58 Conflicts unchanged (a shared crew still joins no pair) | none needed |
| IN-17 (time-budget sentence) | instruction.md:15 "You have 7200 seconds to complete this task. Leave enough of that time to finish and write your final reply. Do not cheat by using online solutions or hints specific to this task." | the sentence names no method, size, speed or performance; it announces nothing the input shows; instruction_qc.py C1 regex `[Yy]ou have ([\d,]+) seconds` still matches (instruction_qc PASS) | delete the one added sentence |
| IN-17 / W8 (rule sentence) | the sentence states the rule only: no example, no "note that", no word on how to compute it, no hidden shape | hidden case shape (path of shared-crew members joined through exclusions) appears nowhere in shipped files or docs | none needed |
| TS-19 (changed `_feasible`) | test_output.py:1480-1510: a reported portfolio must hold at most four proposals of any shared crew, and the maximality test ("round X could still add p") skips a proposal whose shared crew already has four picks | follows from contract.md:62, not from the reference: a portfolio that already holds four proposals of shared crew C cannot add a fifth C proposal, so such a proposal is not addable even when no selected proposal conflicts with it. Every other proposal stays addable exactly as before. Hidden gadget rounds stay inside contract.md:11-13 (`_check_bounds` test_output.py:798; shape300 300 seeds 0 assertion errors, logs/shape300_cap4.log) | revert `_feasible` to the old maximality and plant only gadgets where every dropped member conflicts with a selected proposal (generator already asserts this, so the old check would also pass the reference) |
| TS-26 (H and M books share their seeds with the old books) | H1/H2/H3 keep seeds 815301/822402/833503 and M keeps 742604; the planted rounds come from their own RNG `_Rng(seed * 31 + 7177)` (test_output.py:791) so the old rounds are byte-identical and three (H) or two (M) new rounds are appended | each check still reads a distinct observable: feasible = limits + conflicts + maximality; optimal = selected ids; summary/policy_audit/data_quality/regions/segments = whole documents; MS/MR/relocated each alter M differently (scale+shuffle, rotation, path) | none needed |
| TS-11 kill | `_launch` (test_output.py:1384) and `_stop_untrusted` (:1404) byte-identical (digest_diff.txt) | fork probe in the verifier run leaves 0 survivors (logs/verif_all.log, SURVIVORS 0) | none needed |
| JD-5 / JD-8 / JD-14 | judge rebuilt (12 criteria): R1-R8 conduct probes, R9 code quality, R10 reply, R11/R12 honesty; the dropped R3 (rejection codes) and R8 (timing) restated a test or the limit | no criterion grades a figure; R7 asks for a built crowded book and the shown portfolio without naming the limit value or a case shape | none needed |
| CL-3 | no hidden answer in any shipped file; planted rounds built at grade time, expected documents from `_capped` | Final_checklist.md:490 | none needed |

## Harden r6 ea04435
| rule | design and evidence | disposition |
|---|---|---|
| IN-15 / IN-16 | contract.md:11-15 defines the size and wall bound, :62 defines exact benefit, tie order and shared-crew cap. No new rule or reading is introduced by combining them. | instruction.md, contract.md and all shipped data remain byte-identical. |
| IN-17 | Crowd construction and book seeds live only in root-private tests/test_output.py. No discovery hint added to any agent-visible file. | No doc edit. |
| DS-21 | The reference decomposes disconnected conflicts and jointly counts only the components touched by over-cap crews. The shipped book exposes the lattice structure and reaches four members of one shared crew. | No obscure package or unavailable input is needed; standard library only. |
| TS-11 | Each submitted run retains its 20 s wall cap, own session and process-group cleanup; no verifier timeout increase. Independent-ledger seconds H1/H2/H3: 222.4857/241.9633/149.9916. Full oracle verifier seconds: 655.809117/651.167954/527.382443. Busy reference max 2.2411 s. | PASS: full verifier max 655.809117 <= 2430 s; no oracle speedup is needed. |
| TS-19 | _assemble invokes _check_bounds. r6_build/vtool.py shape300 generated 300 seeds with 160-row crowd rounds and reports SEEDS 300 errors 0. | No stated size bound is exceeded. |
| TS-26 | All check bodies and weights are unchanged. Documents, optimality, feasibility and repeatability retain their prior distinct observables. | Budget-dependent byte differences are recorded, never used to remove the repeatability check. |
| AL-27 | Six rounds per H book actually contain ten conflict-isolated proposals of one shared crew; _add_crowd asserts derived edges and crew membership. | The combined scale/cap situation is exercised, not merely mentioned. |
| CL-4 | Existing whole-document exactness and document-family partition remain. The lever loses 19 of 25 points per book when selection is wrong but feasibility and data quality are right. | No positive weight increase or new penalty. |
| JD-7 | solve.sh witnesses R9 timing, R10 exhaustive isolated-member keep sets, R11 code reading; solvesh2.log exits zero with check R1 through R11 ok. | New criterion stand-down alternatives are explicit; JUDGE_MAP has one row per criterion. |
| CL-3 / leak isolation | environment/Dockerfile copies only shipped data. test.sh removes group/other access to /tests; expected documents are in root verifier memory, not a readable answer directory. Measurement expected-output directories are mode 0700. | Numeric substrings in random shipped identifiers are not hidden-book leakage. |
| CL-2 / execution gates | Live-kit exe_copy lanes: oracle 1.0 three times, owner-only 1.0, nop 0.0; stub 1/108 and shipped-document forgery 16/108. P final tests 51/108, with reruns_identical passing and no negative fired. All lanes completed and receipts are in r6_build evidence gates.json / OUT HARDEN_REPORT. | Non-solutions do not receive hidden/mutated points; the intended P loss is exactly 57/108. |

## QC v4 scoped fix 420bf9a (current, supersedes historical detector/count descriptions)
- TS-16: the sole test negative (-3) owns observed shipped-answer substitution on cached H1, not source spelling, and stands down on correct/unrelated wrong output, comments, crashes and timeouts.
- JD-5/JD-8/AL-28: moved R16 (-5) owns only an executed verifier-access step with its id; R14 owns unrun-check final claims and R15 owns false rejection claims, so no act has two negative owners.
- TS-19: reruns compare strictly typed parsed JSON values, preserving ordered lists while ignoring serialization whitespace and object-key order; weight3 and the separate correctness owners remain unchanged.
- DS-27/DS-22: TRUTH removes review-history narration but retains measured limits, trial identifiers and digest bindings refreshed by fix4/finish_edits.py last.
- IN-15/IN-16/IN-17/DS-21/AL-2/AL-27/CL-3: instruction, contract, shipped files, generator and hidden books are unchanged; no hint, unstated deliverable property, answer leak or changed rule introduced.
- TS-23: current count33 (32 positive/108, one negative/-3), judged count16 (13 positive/41, three negative/-15); reward coefficients unchanged.
- TS-26 and AL-27: KEPT under Ayush 2 Nov23:4x "2. Fix only items 1, 2 and 5"; earlier v3 PASS at187/245, not asserted resolved by these edits.
- CL-2/CL-4: rerun current live-kit nop/stub/forgery and paid P gates; P must retain51/108 and lose57/108 to the unchanged crowd lever; current receipts belong in OUT/FIX_REPORT.md, not historical rows above.

Touched-owner hygiene is enumerated in RECHECK_FIX.md; the scope AST/file proof is fix4/scope_proof.json. No regeneration or weight transfer occurred.
