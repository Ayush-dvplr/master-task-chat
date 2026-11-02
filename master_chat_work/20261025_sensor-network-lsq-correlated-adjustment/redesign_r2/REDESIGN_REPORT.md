# REDESIGN_REPORT r2 (board 4d6dfe8): sensor-network-lsq-correlated-adjustment

Status: DONE. Bundle edited in place (no folder regeneration, no --force). Tree sha before 5823ca803559 (= p12_r3), after 772589ab1588 (69 files). QC kit HEAD 976c1666. Session rename: opencode matched ses_e90a3881effeekr4lU9Ua6qzuV.

## Levers before / after
| | before (r1) | after (r2) |
|---|---|---|
| levers carrying the score | H1 centring, H2 angle reduction, H3 revision, H4 chain; each one sentence naming its exception, shipped rows separating the readings (P14: NO NATURAL TRAP) | A H7 traverse closure second sharing (schema.md:112-129, new `traverse_closure_register.csv`); B H6 recursive set-out chain (schema.md:20-26 and :78, new `control_mark_register.csv`, `set_out_from` column); C H3 district = district of the kept shard (schema.md:54-57, :245) |
| separating cases | shipped and hidden | one hidden extract each (A eval, B challenge, C audit); shipped figures identical under every wrong reading (W5) |
| r1 levers | scored | kept as graded noise |

## Counts and weights
- Tests 30 (28 positive, P = 86; 2 negatives -5, -3). The old 62 points are unchanged; new: visible shipped w3 + hidden `_hard` w5 per lever.
- Shares: hidden reruns 76/86 = 88.4%; shipped-only 10/86 = 11.6%; each lever's family 23/86 = 26.7%.
- Judge 11 criteria, positive 24, batched. R1-R4 figures recomputed (vTPv 999.9232011672, variance 0.9812789020, signed sum -444581, trace 14059330.440663). R9-R11 own-input recomputes w3 (solve.sh prints `check R9 ok`, `check R10 ok`, `check R11 ok`). R5 reworded to the LEVER_RULES J4 shape (`r5_derive_report_py_maintainable`) because precheck failed J4 on the old wording; this departs from master condition 6 ("R1-R8 unchanged").

## Measured (real tests, local, tests channel)
| program | score |
|---|---|
| oracle | 86/86 = 1.000 |
| one lever wrong (A, B or C) | 63/86 = 0.733 each |
| two wrong (AB, AC, BC) | 40/86 = 0.465 each |
| all three wrong | 17/86 = 0.198 |
| a2 agent program (reflex gate) | 8/86 = 0.093, PASS (<= 0.20); passes artifact, control values, superseded, canonical only |

- Final-generator fuzz, 300 corpora per lever: one-lever reflex differs 300/300 (A, B, C), a2 differs 300/300, 0 generator rejects, oracle exit 0 on all.
- G11: 33 contract rules, every mutant fails >= 1 test (WORK/RULE_COVERAGE.md).
- One lever missed at rubric 90 gives overall 81.6 (over 70); under 70 only if the run also skips the matching recompute criteria (WORK/COST_TABLE.md).

## Gates
- STACKING_CHECK: PASS (OUT/STACKING_CHECK.md).
- xref_check: 23 entries, 0 findings. precheck: PRECHECK CLEAN. No __pycache__.
- 4 kit QC scripts: exit 0, 0 warns (X1 binary only).
- validate_bundle.py: 44 pass, 5 FAIL (section 1.12 archetype manifest; 11.2-11.5 recommended negative tests). Same as harden_r1 and present in the converted source; advisory for this bundle; not fixed. playground: no playground.py exists, not run.
- Docker (tests only, judge.toml removed in the container): oracle 1.0, 1.0, 1.0; owner-only 1.0; nop 0.0; stub 0.0116; forgery 0.0698. Copies built with the live kit's exe_copy.py (plain, --owner-only, --stub).

## Not run
- Harbor itself: the harness CLI is blocked by this session's bash permission rules (the deny pattern on the harness run command). The Docker numbers above come from a docker-only emulation of the verifier (same tests image, solve.sh as uid 1000, test.sh as root), not a Harbor run.
- Judge (no API key). Real probe run (master queues it).

## Lessons for the master
- An agent program written before the new rules always differs; the one-lever reflex variants through the real tests are the useful number | no change: master already asked for them
- A defined-term lever that only feeds rollups costs 3/18 per extract; coupling it into the closure groups lifts it to 23/86 | no change: G1 coupling covers it
- precheck's J4 regex rejects a stage-function R5 wording, so "keep R1-R8 unchanged" collides with PRECHECK CLEAN | template_change: prompts should exempt the J4 criterion from "unchanged" lists
- This session's permissions block the harness CLI, so a Harbor Docker block cannot be met here | template_change: issue.py should check session permissions before asking for Harbor runs
