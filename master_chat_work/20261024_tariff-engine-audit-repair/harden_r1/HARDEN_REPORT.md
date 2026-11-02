# Harden round 1 report: tariff-engine-audit-repair (d62ffe6)

Bundle tree after this round: `747b2e0bd036` (sha256 over sorted paths and bytes).
Session rename: ran, list shows `ses_e90f673bcffebCnCl2i7pl1t46`.

## Phase A and cause

- Phase A: GENUINE. Probe 1 ran the staged copy of this bundle with no exception, no
  verifier error and no permission error. It scored tests 121/121, judge 15/24, overall 81.25.
- Primary cause: 4, levers weak by design. The contract named each separating case:
  the malformed list at :77-79, Month = billing period at :43-44, half even per line
  at :42 and :117-119, and the credit base at :121-125. The agent wrote all the graded
  logic in steps 13-17, about 45 s after reading the contract. Fuzz on its program
  found 0 of 341 corpora differing. Full detail is in `DIAGNOSIS.md`.
- `WORK/XREF.md` and `baselines.json` did not exist before this round. XREF.md is now
  written and has 46 entries.

## Levers before and after

| lever | before (probe 1) | after (round 1) | rule written at | habit-slip alone |
|---|---|---|---|---|
| LV-TR-4 strict quantity (H1) | counted, enumerated :77-79, LEAKED | uncounted gate. :85-86 now reads "its `quantity` is not what the `quantity` field rule allows", and :63 keeps the bare type | api_contract.md:63, :85-86 | qty coerce loses 86 |
| LV-TR-3 month = period (H3) | counted, LEAKED | replaced by N2 | - | - |
| LV-TR-2 half even per line (H2) | counted, LEAKED | uncounted gate, stated rule | :49-50, :128-130 | half up loses 75 |
| credit base partial | counted 20.7%, LEAKED | uncounted gate | :132-136 | credit rounded loses 25 |
| N1 allowance re-share (H7) | - | counted | Energy share :46-48, Amounts re-share :125-128, column :69-72 | one or two passes lose 60 (47.2%) |
| N2 calendar month (H3) | - | counted | Month :51, Active days :43, Standing :115-119 | start-month habit loses 45 (35.4%); period length loses 58 |
| N3 account tier position (H6) | - | counted | Account position :38-40, Energy :107-113 (Period quantity :52 stays per meter) | per-meter tiers lose 45 (35.4%) |
| LV-TR-1 amplifier (H5) | kept | kept | :3-5 | - |

- Your N1 wording is applied word for word. I kept the repetition clause "as often as
  some stays unshared and such a line remains", because without it the answer key is
  underdetermined.
- Planting: fresh and rescaled carry N1+N2, relocated and rotated carry N1+N3, and api
  carries N2+N3. Shipped data has one-pass allowances only, periods inside one month,
  and every account total at or below tier-1 `up_to`. Regression cases have the same
  limits.
- Union of the three habit slips: 90 of 127 points.
- Reference crash fixed at tests/test_output.py:5526, now :5607, with
  `Fraction(standing_charge)`. Output was byte-identical on the shipped corpus and all
  five seeded hidden corpora (`crashfix/prove_run.txt`).

## Counts and weight shares

- Tests: 33 checks, 31 positive worth 127 points, plus 2 negatives worth -8.
- Judge: 13 criteria, 30 positive points and 13 negative, batched. R12 (third allowance
  share probe) and R13 (account tier crossing probe) are new at weight 3, and solve.py
  prints `check R12 ok` and `check R13 ok`.
- Shares, counted by reading the code: hidden and mutated reruns 96/127 (75.6%), of
  which mutated is 35 (27.6%). Shipped-only is 14 (11.0%), whole-doc is 0, deliverables
  are 17 (13.4%). The tool's heuristic labels 64.6% as isolated; that figure is
  corrected in `STACKING_CHECK.md`.

## Gates

| gate | result |
|---|---|
| reflex: probe-1 agent program on new tests | 0.1811 (23/127) PASS (<= 0.20) |
| STACKING_CHECK | STACKING PASS |
| G10 all-but-one overall < 70 | FAIL at a rubric of 90 (71.4, 77.3, 77.3). PASS at the measured probe-1 rubric of 62.5 (57.6 to 63.5). Reported as measured, not gamed |
| G11 rule coverage | 57 mutants, 0 uncovered, none fires a negative |
| differential fuzz (new generator, agent program) | N1 74/74, N2 74/74, N3 79/79 corpora differ; lever-free family 0/79 |
| precheck (kit 976c1666) | PRECHECK CLEAN, 0 warnings |
| validator `--archetype repo-patch` | 40 passed, GATE PASS |
| xref_check | 46 entries, 0 findings |
| Docker oracle x3 | 1.0, 1.0, 1.0 |
| owner-only | 1.0 |
| nop | 0.0 |
| stub | 0.0 |
| forgery (replay of shipped answers, no compute) | 0.2047, MISS against the 0.05 target |

- The forgery scores 0.2047 because deliverable reports, determinism, missing-source
  and shipped replay all pay without a working program. The hardcoding negative fired
  (-5).
- A no-program forgery (oracle reports plus the unrepaired source) scores 0.0945
  locally.
- Not fixed: closing this would mean tying the deliverable checks to hidden results.

## Not run

- `playground.py` was removed upstream.
- No agent probe was run in this round.
- No judge run on the new trajectory criteria.

## Lessons for the master
- A spelled-out re-share rule needs its repetition clause, or the key is underdetermined | no change: kept in the contract, reported here
- Parallel run_checks scored the oracle 0.8976 from contention, and 1.0 when run alone | no change: rerun the oracle alone before trusting variant tables
- Replay forgery earns 20% from deliverable and shipped checks | template_change: _COMMON_RULES_v3.md forgery line, measure it before Docker
- stacking_check labels hidden-corpus reruns as isolated | no change: correct by reading the code, as done in STACKING_CHECK.md
