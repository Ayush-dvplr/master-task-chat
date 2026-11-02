# HARDEN_REPORT - district-heat-flex-procurement, board 8d509b8 (gate v3.6 judge harden, Option B)

Session renamed (opencode match `ses_e7e8b989cffeSifz08toHv9AkZ`; codex no match). QC kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (expected).
Phase A: the staged a11 copy equals BUNDLE in tests/ and environment/; task.toml differs only in the staging `allowed_hosts` lines.
Master unlock (verbatim scope): "go B. solution/solve.sh is unlocked for the four oracle demo stages only (inside the existing '|| true' self-check block ...)".

## What changed (G7)
`diff -rq` BUNDLE vs the pre-round Tasks_INPUT copy (= frozen b18d48a1deda) before sync: only `tests/judge.toml`, `solution/solve.sh`, `solution/TRUTH.md`.
tests/test_output.py, reward.toml, instruction.md, environment/ (docs, data), solution/solve.py byte-unchanged.
solve.sh lines 1-229 (oracle run + shipped-data self-check) byte-unchanged; only the `|| true` own-extract stage changed:
- extract 4 (solve.sh:434-441) now one chosen offer with interval amounts 1.5 and 2.5 cents -> 2 + 2 = 4 (half up would give 5);
- new altered copies of /app/data under the same temp dir (never /app/out): 5 pools (solve.sh:451-472), 6 allowance (:473-492), 7 uplift (:493-510).
  Each prints a plain line "altered copy of the shipped extract, <what>: program X, recomputed outside the program Y, agrees" (no R/J numbers, DS-17).
Docker test of solve.sh (13:29): exit 0, rerun exit 0, every line "agrees", /app/out holds only the 9 JSON + derive_report.py.

## Arithmetic
Before (a11): tests 73.0 (173/237), rubric 62.5 (15/24), final 67.75. a10 (older tests): rubric 16.67 (9 - 5 R7) / 24.
Tests unchanged, so tests stay 73.0 (restated from a11; no kill test, no cost re-run per master note 5).
After (predicted, positives only, no negative fires): a10 3/24 = 12.5%, a11 3/24 = 12.5% mid; upper 6/24 = 25%.
Final mid (73 + 12.5)/2 = 42.75; worst (73 + 25)/2 = 49.0 < 50. Gate: tests 73 < 85, rubric <= 25 < 85, final <= 49 < 50.

## Judge (tests/judge.toml), positive 24, R7 -5, reward.toml judge 0.5/24 unchanged
| id | file:line | w | type / target | a10 | a11 |
|---|---|---|---|---|---|
| R1 drawn allowance own extract | judge.toml:13 | 3 | behavior / trajectory | no (unchanged) | no |
| R2 start order own extract | :26 | 3 | behavior / trajectory | no | no |
| R3 composed rate above cap own extract | :39 | 3 | behavior / trajectory | no | no |
| R4 two half-cent interval amounts (NEW wording) | :52 | 3 | behavior / trajectory | no | no |
| R5 exact arithmetic | :65 | 1 | instruction following | yes | yes |
| R6 final run after last edit | :78 | 1 | behavior / trajectory | yes | yes |
| R7 claims a check its output contradicts | :91 | -5 | factuality / message | fired in a10 | no |
| R8 rerun, pool too small for claims (NEW) | :104 | 3 | behavior / trajectory | no | no |
| R9 rerun, allowance below a chosen offer (NEW) | :117 | 3 | behavior / trajectory | no | no |
| R10 rerun, uplift lifts rate above cap (NEW) | :130 | 3 | behavior / trajectory | no | no |
| R11 maintainable derive_report.py (J4) | :143 | 1 | behavior / state_change | yes | yes |
Weight shares: probes R1-R4, R8-R10 21/24 = 87.5%; R5, R6, R11 3/24 = 12.5%. Criteria 11 (10 positive, 1 negative). Tests 66 checks / 237 points (A3 warn, option A).

## Per-criterion evidence (trajectory steps)
- R4: a10 step 24 synth extract has one 1.5-cent interval (judge a10: "50 credited ticks x 10 Wh x 3000 / 1,000,000 = exactly 1.5 cents"), not two half-cent amounts; a11 steps 27-28 one 0.5-cent interval plus a 1-cent one (judge a11: "first-interval amount of exactly 0.5 cent ... its second interval contributes 1 cent"). Both no.
- R8: neither run copies /app/data and lowers a pool. a10 step 28 and a11 steps 33-34 recompute grants on the shipped data only (a11: "All shipped pools fall in the claims-paid branch"). a10 step 24 has a shortfall branch, but in a hand-built synthetic extract, not a copy of /app/data: the borderline case counted in the upper bound.
- R9: a10 step 28 replays allowance counts on shipped data; a11 step 34 "verifies every selected offer" on shipped data; no altered allowance rerun. Both no.
- R10: a10 step 27 and a11 step 33 recompute credit on shipped data; neither raises an uplift in a copy. Both no.
- R1-R3: unchanged, both no (judge reasons quoted in OUT/DESIGN.md).
- R5, R6, R11: both yes (a11 R6: "After the final source edit in step 32, step 33 runs python3 out/derive_report.py data out").
Neither run altered a copy of /app/data at all (a10 steps 32/36 rerun to relocated output dirs with unchanged data), so R8-R10 share one skipped habit. That correlation is the main risk: a careful agent doing P-d would gain up to 9.

## Touched-rule table (G4)
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| R4 | re-targeted: two half-cent amounts, even and odd cent below | JD-2, JD-5 (one act), JD-6 trajectory, JD-7 oracle extract 4, JD-9, JD-13, JD-14 (no other criterion pays half-even), JD-15 tie instruction.md:3, :9, AL-2, AL-28, IN-15 | PASS |
| R8 | re-targeted: rerun on copy with a pool too small for the claims | same set; JD-7 oracle altered copy 5; JD-14 vs grants tests: process, not output, not re-charging a tested trap | PASS |
| R9 | re-targeted: rerun on copy with allowance below a chosen offer | same set; JD-7 oracle altered copy 6 | PASS |
| R10 | re-targeted: rerun on copy with uplift raising a rate above cap | same set; JD-7 oracle altered copy 7; JD-14 vs R3 (own extract vs altered shipped copy, different act) | PASS, fallback recorded (recipient weight zero) |
Vacuity (G5): an agent that changes nothing earns no positive point (R6, R11 need a delivered program; R5 needs a program; probes need acts). Each probe is reachable from schema.md plus instruction.md:3 ("It will also be run on other extracts in the same schema ...").
R7 unchanged (master: "Keep R7 as it is").

## Gates
- xref_check: 49 entries, 0 findings. TRUTH.md regenerated last by WORK/w1_truth.py (fix_patch sha matches solve.sh).
- STACKING_CHECK: STACKING PASS (OUT/STACKING_CHECK.md).
- precheck last line: `PRECHECK CLEAN` (4 QC scripts exit 0, warns 0; A3 66-check warn recorded, option A; no IN17/G5 warns).
- validate_bundle.py --archetype domain-calculation: 40 passed, 0 failed, GATE PASS (OUT/validate_bundle.txt).
- Docker gate block (tests only, exe_copy copies): oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, stub 0.0042 (1/237), forgery 0.2489 (59/237, unchanged); every oracle and owner log has 0 DIFFERS lines; solve 10 s; chain /tmp/opencode-logs/dh-8d509b8/dchain-20261028T1338/ ALL_DONE 13:42:04, lock released.
- Tasks_INPUT: judge.toml, solve.sh, TRUTH.md copied with `cp -p`; `diff -rq` BUNDLE vs Tasks_INPUT copy: empty. No __pycache__/.pyc. Tree sha (peer_manifest root_sha rule): 34a4d2f3e198.

## Not run
No kill test, no cost table re-run (tests unchanged, master note 5), no blinds, no judge execution (judge.toml validated by exe_copy, not executed), no harness run.

## Lessons for the master
- With solve.sh and reward.toml locked, a judge-only harden cannot remove points the oracle already shows on shipped data; a careful run copies those acts. Unlock the oracle demo stage early when the probe acts both runs skipped are fewer than needed.
- Altered-copy reruns (P-d) were skipped by both Opus runs; three P-d probes are one correlated habit, so the worst case is one run that does P-d well (+9).
- The tree sha label (b18d48a1deda) does not match git write-tree or peer_manifest root_sha; state the hash rule with every tree sha.
