# DESIGN: match-replay-desync-audit (reconstructed, pre-harden)

Source: converted bundle (QC assigned/converted tasks), conversion notes, verify notes, solution/TRUTH.md.

## Story
A turn based strategy build wrote replay captures through twelve wire transforms selected by a header
flag word. Eleven numeric quantities (nine transform parameters, cadence modulus, upkeep target scale)
are withheld; calibration.md publishes one control figure per quantity in pin order. The agent writes
/app/out/optimize.py <capture dir> <report dir> that recovers the quantities, decodes every capture,
settles the entries (identity chase, live windows, earliest-uncancelled reversal matching with
promotion, charter caps, coupled charter stocks solved exactly, cadence classes, exact bench subset)
and writes eight reports plus bottleneck_analysis.json.

## Data (environment/data)
replay-format.md, engine-rules.md, charter-scale.md, calibration.md, report-schema.md,
example-scenario-report.json, roster-register.csv, tick-schedule.csv, bench-candidates.csv,
captures: calib_wisent, field_marrow, field_quarry, field_tundra, sample_cobalt, sample_orchid (.rpl).

## Grading (pre-harden)
- tests/test_output.py: 40 checks, positive 163, negative -23. 3 at w1, 4 instance w5, 12 trap_*_inverse w5
  (one per transform, held-out capture set with only that bit live), 16 general_* w5 (held-out reseeded
  sets, mutated), 5 negatives.
- tests/judge.toml: 18 criteria, positive 43 (R7..R13 are 'states figure X' outcome criteria, w5 each), negative -21.
- reward.toml: test_output 0.5/163, judge 0.5/43.

## Focal points (TRUTH.md)
eleven quantity recovery in pin order; earliest-uncancelled cancellation with promotion; coupled charter solve.
Traps: all twelve transforms at once, chained mask sequential, filler lines invisible to check, rotation and
permutation invisible, donor table ring.

## Harden P9 v2 r1
Diagnosis: Phase A GENUINE, primary cause 4 (every transform and engine rule stated plainly and exercised
together in shipped captures with controls fingerprinting each stage). Run 0.8043; the 12 trap failures came
from the agent's uniqueness assertion induced by the instruction promise, not from any lever.

Cancellation order partition (P12 v3 r5, QC v5 F1 CL-4): only the shipped set and the reversal density and
tiebreak sets let earliest and latest cancellation part (`_grades_order`, divergence planted there); every
other corpus is repaired by `_settle_one_order` so both orders settle alike. A latest-entry reading now costs
15 of 172 (instance x5, general_reversal_density, general_reversal_tiebreak), not 171.

Levers L1 + L3 + L4 (see LEVERS.md):
- L3: per-entry charter cap replaced by a running per-charter allowance (size baseline times units the register
  opens) drawn by settled entries in walk order after reversal matching (charter-scale.md:70-79,
  engine-rules.md:59-60).
- L4: allowance renewed at the first tick of every live window (engine-rules.md:44-45) composed with
  roster-register.csv, tick-schedule.csv and the walk order.
- L1: calibration controls, header seal and the reconciliation identity stay green under every amount misread.

Data: shipped corpus unchanged except notes text; hidden corpora scale entry amounts by HELD_OUT_HEFT = 40 so
allowances bind. Generator tweaks added: ('value', name, v) and 'split' for the two mutation tests.

Grading: tests 42 checks (6 shipped w1, held-out derivation record w3 (P12 v3 r2 W2) and report listing w1,
28 hidden whole-document w5, 2 mutation w5, 4 negatives -5), positive 160, negative -20; first differing path
printed per failing check. Judge batched, 11 criteria,
positive 17 (R1-R5 w1 process, R7-R9 w3 conduct one per lever, R11 w3 code quality of /app/out/optimize.py, J4), negative -8 (R6 -3, R10 -5).
reward.toml 0.5/160 and 0.5/17. Instruction: removed shipped-slice uniqueness promise and judged figure list;
added G5 sentence and the one-file sentence (P12). Format: chown root + chmod 755 /logs/verifier, pip pin with
litellm 1.105.0, _grant_read. P12: every fresh corpus draws its eleven quantities from the published candidate
sets by seed (drawn_values, pins_separate repair, class_draws_renamed repair for per cadence sets).
Local reflex replay: real agent program and adapted copy 20/160 = 0.125 (P12 v3 r2; was 18/158); oracle passes all 38 positives;
a program carrying the shipped eleven values earns 6/160 = 0.038.

## Control fragment serialization (published, P12 v3 r2 F1)
The fragment recipe of every control CTRL-A..K is published in calibration.md, section "Fragments each
control reads", generated from FRAGMENT_RECIPE in tests/test_output.py and identical on every staged
corpus. It was withheld until QC v2 (fba1605) failed DS-21; Ayush Q54 (24 Oct) reversed the withholding.
WORK/grammar_check.py proves the text is enough (11/11 shipped and held out).

## P12 v3 r6 (c45716e)
instruction.md no longer states the quantity count, the transform order note, the zero-flag captures, the
roster announcement, the coupled-stock method, the float warning or the bench uniqueness (IN-17); the notes
carry each. Decoded fields count every decoded entry (report-schema.md:13-15). Exact-match sentence at
instruction.md:13. Reads-answer negative is now a planted-decoy behavioural run.
