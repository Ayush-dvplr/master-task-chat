# sentinel-policy-recompute: test-hardening round t1 (board b7e15f9, 26 Oct 2026)

Session rename: `name_session.py b7e15f9` printed `codex: no match / opencode: ['ses_e87300d24ffe0mEYurecnYSop9']`; b7e15f9 itself was not shown in the list. Not retried.
QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Judge kept exactly (d0f1870, 15 criteria); no new probes.

## New quiet rules (each one plain sentence plus one toy example on invented values)
| id | rule | written at | reflex reading it catches |
|----|------|------------|---------------------------|
| Q1 | running timeout floor 1000 ms, applied amounts taken one at a time in ascending seq | `environment/data/units_reference.txt:8` (example :9) | base + sum (probe-4 cli.py:406); clamp once at the end |
| Q2 | reissued override_id: only the highest-seq row is that override | `environment/data/override_deltas.json:6` | every row drawn on its own |
| Q3 | `param_key_aliases` maps an alias to a principal inside a half-open span only | `environment/data/override_deltas.json:4` | `param_key == principal` only; alias honoured outside the span |
| Q4 | `requires`: applied only when the named override was applied earlier in the same draw (replaces the retry cap, per master note 2) | `environment/data/override_precedence.conf:7`, field named at `override_deltas.json:11` | field ignored; order-free check |
| Q5 | superseded row with `carry` adds that one delta for its principal when its window and versions match, without being applied or drawing | `environment/data/override_deltas.json:13` | superseded rows skipped; carry honoured outside the window |

No new key appears in shipped data (no `param_key_aliases`, no `requires`, no `carry`, no repeated override_id); the floor value is stated only inside its sentence. No "note that", "unlike", "even when" wording; the five sentences sit apart in the files that own each family.

## BRANCH_FIRE (WORK/BRANCH_FIRE.md)
| rule | shipped | q*-a | q*-b | combo-a / combo-b | old 16 corpora |
|------|---------|------|------|-------------------|----------------|
| Q1 | 0 | 3 | 2 | 2 / 2 | 0 |
| Q2 | 0 | 2 | 3 | 4 / 4 | 0 |
| Q3 | 0 | 4 | 3 | 5 / 5 | 0 |
| Q4 | 0 | 2 | 2 | 2 / 2 | 0 |
| Q5 | 0 | 2 | 2 | 2 / 2 | 0 |
Each owned corpus fires only its own rule. The combo corpora (RNG `sentinel-combo-<seed>`) plant 7 rare pairs on single records (alias+requires, reissue+alias, alias+floor, alias+carry, reissue+requires, reissue+floor, reissue+carry). Old corpora give byte-identical documents to pre-t1. The generator checks bounds; 300 seeds x 6 families gave no crash and min fires 2.

## Counts
Rules 36 over 20 files in 11 formats (WORK/RULE_TRACE.md). Tests: 23 checks (20 positive, P = 80; 3 negatives -11). Judge: 15 criteria. reward.toml test_output 0.00625 (0.5/80), judge 0.0125.
New checks: five owned `hidden_*_hard` checks weight 5 (whole policy, curve and graded trace exact on 2 seeded corpora each) plus `hidden_rare_rule_pairs_hard` weight 3. Shares: quiet 28/80 = 35%, all hidden or mutated 76/80 = 95%.
Weight 4 was refused by tests_qc W2, so it moved to 5 and P went from 75 to 80.

## Measured cost table (local, oracle tool with one reading swapped; OUT/local/levers.log)
| program | tests |
|---------|-------|
| q1-sum, q1-final, q2-none, q3-none, q4-none, q4-anyorder, q5-none (each alone) | 72/80 = 90.0 |
| q3-nospan, q5-any (alone) | 75/80 = 93.75 |
| all-but-one (worst single miss) | 90.0 |
| first write (all five skipped) | 52/80 = 65.0 |
| probe-4 agent program, re-scored | 52/80 = 65.0 |
The rare-pair check is charged only through the pairs: each primary reading fails its own check plus the pairs check, and the secondary readings fail only their own check. RULE_COVERAGE: all 27 old mutants still fail at least 1 check at P=80; uncovered rules 0.

## Gates
- STACKING_CHECK: `STACKING PASS` (OUT/STACKING_CHECK.md; tool hints corrected by hand, penalty groups split).
- PRECHECK last line: `PRECHECK CLEAN` (0 IN17/G5 warns; only the X1 binary note). The 4 QC scripts returned exit 0 with 0 warns. Validator: 37 pass, 3 fail (§15.5-15.7 TRUTH yaml provenance block; these were already failing in r2 and r3).
- To clear IN17-PHRASE, I edited `instruction.md`. I dropped the sentence "Several of those files are superseded or retired." and the clause "and never a superseded or retired value". "two runs" became "runs" and "seven artifacts" became "artifacts". All are recorded in QC_DEFENCE.
- xref_check: 72 entries, 0 findings. TRUTH shas were recomputed by script as the last edit.
- Docker (tests-only copies from the live exe_copy.py, TS 20261026T220408-63b2, OUT/local/docker_runs.log, all rc=0, ALL_DONE 22:07:59): oracle x3 = 1.0 / 1.0 / 1.0 (80/80), owner-only 1.0, nop 0.0, stub 0.0, forgery 0.025 (2/80: the hardcoded-answer negative fired and every hidden check failed).
- Tasks_INPUT: `cp -Rp` of the bundle, after which `diff -rq` BUNDLE vs Tasks_INPUT is empty. No __pycache__ or .pyc.
- Tree sha (sha256 over sorted per-file sha256): 72ef50aaadb8.

## Not run
No agent or judge probe (by instruction). No P13 blind read (master issues it).

## Lessons for the master
quiet rules need an all-reading acceptance in the generator (each wrong reading must change the doc) or a corpus silently tests nothing | no change: generator asserts it
tests_qc W2 allows only odd weights 1/3/5, so plan cost shares on 5 and 3 | template_change: _COMMON_RULES_v4.md weights line
old IN17 phrases in instruction.md surface once precheck demands 0 warns; budget a wording pass | no change: recorded in QC_DEFENCE
