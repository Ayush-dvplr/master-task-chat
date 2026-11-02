# Stale build scripts (marked 22 Oct 2026, harden round 2). Never run these.

The bundle was edited in place in rounds 1 and 2. These scripts still emit the round 0 or round 1 format:

- `datagen.py` - writes the round 0 data (program.ini without `[export]`, waiver file without valid signed pending rows).
  The shipped data was patched by hand in round 2 (see LOG.md); regenerating would undo it.
- `make_*`, `TRUTH.src.md`, `judge_r0.toml`, `judge_build.py`, `judge_build_r0.py` - old judge and TRUTH sources.
  Replaced by `judge_build_r2.py` (writes tests/judge.toml and tests/reward.toml) and a hand-written TRUTH.md.
- `score_p3.py`, `grade.py` solver scoring with the S0 to S5 lazy solvers and `wrong/` - the round 1 hardness method.
  `grade.py` itself still works for a single workspace (host python, stub rewardkit).
- `solve_r0.py`, `test_output_r0.src.py`, `schema_r0.md`, `instruction_r0.md`, `LEVERS_r0.md`, `LEVERS_r1.md`, `DESIGN_r1.md`
  - frozen copies of earlier rounds.

Current, usable: `test_output.src.py` + `embed.py` (writes tests/test_output.py), `judge_build_r2.py`,
`lever_table.py`, `check_exact.py` (exactness against plain enumeration), `grade.py`.

Harden lp1 r1 (23 Oct 2026): `judge_build_r2.py` is now stale (tests/judge.toml and reward.toml were hand-edited for the 8 lp1
criteria). Current: `lp1_data.py` (applies the lp1 data edits from `lp1_src/` originals), `test_output.src.py` + `embed.py`,
`lever_table.py` (now with combined readings), `grade.py`. `check_exact.py` is unchanged (search only).

Redesign r4 (25 Oct 2026, board 7743264): current scripts are `r4_data.py` (shipped data edits from `bundle_pre_r4/`;
already applied, do not re-run on the edited bundle), `r4_tests.py` (one-shot rewrite of `test_output.src.py`; already
applied), `r4_truth.py` (writes solution/TRUTH.md from `TRUTH_r4_body.md` + sha lines; re-run after any tests/ or
solution/ edit), `test_output.src.py` + `embed.py`, `grade.py`. Stale now: `lp1_data.py`, `lp2_data.py`,
`lever_table.py`, `judge_build_lp2.py`, `check_exact.py` (r2 rules), `TRUTH.src.md`. Frozen copies: `bundle_pre_r4/`,
`test_output_r2.src.py`, `XREF_r2.md`.

QL2 fix 19f8e1f (2026-10-29): current scripts `p12q2/ql2_data.py` (one-shot receipt edit, applied), `p12q2/truth_edits.py`
(one-shot edits of `TRUTH_q2_body.md`, applied), `p12q2/repair_src.py` (one-shot, applied), `p12q2/gen_wide_truth.py`
(recomputes `_WIDE_TRUTH`; its `--write` regex is unsafe, never use `--write`), `p12q2/check_repair.py`, `q2_truth.py`
(writes solution/TRUTH.md from `TRUTH_q2_body.md` + sha lines; run last). Pre-edit copies: `p12q2/src_before/`.
