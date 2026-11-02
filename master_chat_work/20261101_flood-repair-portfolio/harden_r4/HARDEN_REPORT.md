# Harden r4 ea94780: flood-repair-portfolio (off route 1, shared-crew limit)
Status DONE (Phase 0-3). Final rename: opencode db query timed out after 60 s, "NOT RENAMED" (first rename at 20:00 had succeeded); not retried. Design: DESIGN.md (DESIGN READY, candidate A). Session rename: `opencode: ['ses_e687bf897ffeELcDEuw18nYS48']` (codex no match). Kit HEAD 5574d77e. Tree before 931f8f817d76, after 7d68065946fd (BUNDLE = Tasks_INPUT).

## Diagnosis
r3 NO CORE: a3 program matched the reference on 1,500 generator books + 141 cases; no wrong fact left in the docs and time cannot separate a3 (5-8 s) from the reference. Only a docs change can open a case. TRIP.md lists where a3 applies each rule: its core is pure graph MWIS and shared crews make no edge (derive_report.py L266-272), so a new shared-crew rule lands as a filter before `plan()` or a trim after it.

## Docs changed
- environment/data/contract.md:62 old: "A portfolio of a planned round is a set of its proposals with no two in conflict. Its total benefit is ..." new: "A portfolio of a planned round is a set of its proposals with no two in conflict. A crew whose mode is `shared` can work on at most four of the proposals in a portfolio. Its total benefit is ..." (rest of the paragraph unchanged).
- instruction.md:15 old: "You have 7200 seconds to complete this task. Do not cheat by ..." new: "You have 7200 seconds to complete this task. Leave enough of that time to finish and write your final reply. Do not cheat by ..." (instruction_qc C1 matches; no speed words).
- Docs consistency grep (`portfolio|conflict|shared|mode` over environment/data and instruction.md): contract.md:3 (funds a portfolio, not a definition), :12 conflict-record limit, :25 sites register shared by all rounds, :27 "`crews.tsv` with columns `crew`, `mode`. Mode is `exclusive` or `shared`.", :54/:56 conflict sources (crew only for `exclusive`), :62 the only portfolio definition (new sentence), :64 figures from the chosen portfolio, :70/:72/:74/:76 output docs refer to the chosen portfolio. instruction.md: no hits. Shipped crews.tsv modes: 1454 exclusive, 946 shared. One definition, so consistent.
- Shipped answers changed: none (round R62233 crew C2534 has four proposals, proposals.csv:48/51/52/56, all chosen; cap 3 would have changed it, hence four). Shipped data files unchanged.

## New and changed checks (tests/test_output.py)
- Generator branch `_capped_round` L647 / `_capped_round_inner` L656 (CAP L570, `_indep_sets` L573, `_capped_rivals` L590, `_codes_peek` L753); `make_book` L791 own RNG `_Rng(seed * 31 + 7177)`. Gadget: one shared crew with 6-8 proposals in 2+ chains of 1-4, neighbours joined through an exclusive-crew proposal; uncapped optimum takes 6+, capped optimum unique, every dropped member conflicts with a taken proposal, optimum differs from 7 shortcut readings; asserted over 300 seeds (shape300 SEEDS_OK 0 300, SHIPPED_DIFF_ROUNDS []).
- _BOOKS: H1/H2/H3 `'capped': 3`, M `'capped': 2`, seeds unchanged, new sha256 (H1 1ab78773807c, H2 f872e825e4cf, H3 d5b89c122897, M 76ef9d6fd8a2; SHIPPED unchanged 51e03c506297).
- Embedded reference: `_Ledger._settle` L1124 `chosen = _capped(info, joined, self.mode)`; `_capped` L1260 enumerates every keep-four choice and re-solves (independent of solve.py's count-state DP); crosscheck SEEDS_SAME 0-300, H1c/H2c/H3c/Mc and shipped identical.
- `_feasible` L1480-1510: asserts no shared crew holds more than four picks (L1503) and exempts from maximality a proposal whose shared crew already holds four (L1507). Follows from the doc: such a proposal cannot be added without breaking the new sentence.
- Digest (funcdigest per block): changed only head (import itertools), _BOOKS, _Ledger (one line), make_book, _feasible; new CAP, _capped, _capped_rivals, _capped_round, _capped_round_inner, _codes_peek, _indep_sets. `_optimal`, `_launch`, `_stop_untrusted`, registrations and weights byte-identical (WORK/h4_rule/digest_diff.txt).
- solution/solve.py: CAP L212, `best_set` L215 with (frontier mask, counts) state, `choose` L261 binds pieces touching an over-full shared crew. solve.sh: cap-aware enumeration, new `check R7 ok (round R10173 on one shared crew: [...])`, `check R8 ok (round R13426: 2 portfolios share the greatest total; ...)`.

## Judge (tests/judge.toml, 12 criteria, judge_qc PASS; reward.toml judge 0.5/32)
Kept probes a3 skipped: R1 VALUE benefits, R2 PAIR sources, R3 region, R4 segment rollups, R5 small rounds by enumeration, R6 altered copy (w3 each). New R7 (w3) runs program on a built book where one shared crew has more than four proposals in a planned round and shows the chosen portfolio (no cap value, no gadget); R8 (w1) shows a shipped tied round with the chosen id list. R9 maintainable w5 (J4), R10 lists rejected rounds w5, R11 J3a -5 unchanged, R12 J3b -5 names a kept round as rejected. Dropped old R3 rejection codes and old R8 timing (restatement). Positive 32, probes 22 = 68.75%.
Grades: natural a3 / a1 low 0, mid 31.25, high 40.6. Actual a3 trajectory (timed out, no reply): low 0, mid 15.6 (R9), high 25.0 (R9+R5).

## Kill table / cost table (Docker 4g/2 cpus, final tests, logs/verif_all.log)
| program | shipped s | verifier s | tests of 108 | lever pts kept of 89 |
|---|---|---|---|---|
| oracle | 7.14 | 64.2 | 108 | 89 |
| a3 correct (keep-four enumeration) | 0.39 | 85.47 | 108 | 89 |
| a3 natural (post-step trim, a3_natural.diff 21 lines) | 0.28 | 73.86 | 31 | 12 |
| a3 prefilter (keep top four) | 0.45 | 91.08 | 31 | 12 |
| a3 unchanged | 0.37 | 84.36 | 31 | 12 |
| a1 | 2.03 | 161.19 | 19 | 0 |
| all-but-one | 8.06 | 161.38 | 19 | 0 |
| first-write | 900.62 killed | 215.18 | 3 | 0 |
| fork probe | n/a | 242.33 | 0 (0 survivors) | 0 |
Reference busy 0.96-2.52 s, unbusy 1.19-3.42 s (limit 20, bar 5). Verifier worst 242.33 s (bar 2430).

## Arithmetic and predictions
Lever share (LV-CAP 86 + timeout reruns 3) 89/108 = 82.4%. Natural a3: tests 28.7, judge mid 31.25, final 30.0. a1: tests 17.6, mid 31.25, final 24.4. Careful correct adaptation: tests 100, recorded (not a blocker).

## Gates
- stacking_check: OUT/STACKING_CHECK.md (AL-28 PASS, G3 60.2% PASS, TS-26 groups covered by QC_DEFENCE).
- precheck last line: `PRECHECK CLEAN` (4 QC scripts exit 0 warns 0; 0 IN17/G5 warns). Validator: 41 passed, 0 failed, GATE PASS. xref 36 entries 0 findings. No __pycache__.
- Harbor lanes (_runs/20261101/flood-repair-portfolio/hardengate4-20261101T230955): oracle 1.0 x3 (plain__cexp4qK 102.49 s, plain__8NMArzX 99.39 s, plain__sZ6RfwN 105.76 s), owner 1.0 (101.22 s), nop 0.0 (83.44 s), stub 0.0093 (artifacts only), forgery 0.1481 (16/108, shipped only).
- Tasks_INPUT: `cp -Rp` BUNDLE over copy; `diff -rq` empty; both trees 7d68065946fd.
- WORK docs: LEVERS, COST_TABLE, QC_DEFENCE (IN-16/DS-21, IN-15, IN-17, TS-19, TS-26, TS-11), EVIDENCE_MAP, JUDGE_MAP, TRUTH.md (truth_update4.py, TRUTH_OK 234 lines).

## Not run
No blind or real agent runs; no live judge call (grades are by hand); no paid run.

## Lessons for the master
- An exact program needs a docs change; pick the rule where the agent's core has no hook (shared crews make no edge) | no change: covered by route-1 notes note 1.
- Check the cap against the shipped data before choosing its value (cap 3 changed R62233) | no change: one-off bundle fact.
- A new selection rule can break an old feasibility check (maximality); list it as a check change | template_change: LEVER_RULES_v3.md section 2 (add "re-derive _feasible under the new rule").
