# DESIGN, dispatch-plan-reoptimization

## v0 (reconstructed from the bundle and the conversion notes)

Converted from a pytest bundle (30 checks, P 91) to rewardkit: every old test
wrapped by one `@criterion`, judge.toml filled to 25 criteria (P 78). The task:
55 opaque exports, a manifest sqlite (`sources` table with role/authority/count),
a handbook contract, and a faulty previous run whose report lists every wrong
assumption. The agent writes a stdlib optimizer that rebuilds coefficients
(cutoff, scale, EUR, amendments, override, energy uplift), solves an exact
capital knapsack, per item lot sizing DP and cheapest first sourcing, and
publishes 21 artifacts. v0 graded 86 of 91 points byte for byte on the shipped
run, plus two 5-point solver reruns (fresh copy, seeded perturbation).

v0 outcome (claude-opus-5): tests 27/91, of which 10 points were lost to the
permission trap (solver 0711, run as nobody unreadable); real tests 37/91. One
lever held (K13 lot tie), 17 leaked. See OUT/DIAGNOSIS.md.

## Harden round 1

Goal: tests score for a careful solver 0.10 to 0.20 with partial credit, no
hidden rules, difficulty from composition and the dependent chain.

1. Grading moved to four hidden input sets (shipped data plus overlays: reseeded
   governing figures in 16 registers, appended register rows, refreshed manifest
   counts). Goldens per set made offline by the oracle. Parsed comparison, not
   bytes. Seven groups per set; only `all_artifacts_exist` reads the shipped run
   (1 of 101). Isolated groups (coefficients 3, capital 1, quality 3) are 28 of
   101; chain groups (plan 5, sourcing 5, totals 5, certificate 3) carry the rest.
2. Grader stages a 0644 copy of the solver, runs it as nobody in its own session
   under a file lock, kills its process group and leftover nobody processes.
   Negatives stand down unless the solver ran cleanly.
3. New levers (LEVERS.md): LV-DPR-01 lot tie order (A), LV-DPR-02 per item setup
   fallback with control default decoy and K22 omitted (B, scope by omission,
   split across runbook and lifecycle log, rare shipped boundary K14 P06),
   LV-DPR-03 first live amendment copy (C), LV-DPR-04 rejection and void
   accounting (F).
4. Instruction cut to the end state: no trap topic list, no rule names, no
   shebang or executable bit (the grader runs `python3` on a staged copy), five
   figures asked for the final reply.
5. Judge: five figures for the shipped run that need the whole chain, one code
   criterion (integer cents), one honesty negative, one /app/data negative.
6. Format fixes: litellm 1.105.0 pin, judge `mode = "batched"`.

Scores (local, stub rewardkit): oracle 1.0, v0 agent 17/101 = 0.168, nop 0,
forge 1/101, single-lever mutants 0.17 to 0.88.

Author-time tools live in `_work/.../build/` (mkhidden.py, mktests.py,
rebuild.sh, oracle.py); they are not shipped.
