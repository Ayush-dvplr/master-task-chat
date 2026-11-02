# HARDEN_REPORT, dispatch-plan-reoptimization (eedf614, P9 harden r1)

## Diagnosis summary
v0 run (claude-opus-5): combined 0.6419, tests 27/91 = 0.297, judge ran 77/78. The permission trap fired: the agent's solver.py ended at 0711 and the verifier ran it as nobody without a readable copy, so both 5-point rerun checks failed. With the trap removed the tests score is 37/91 = 0.407 (verified locally outside Docker). One lever held (K13 lot tie), 17 leaked: the previous-run report listed every wrong assumption, the instruction listed the trap topics, and 86/91 points graded the shipped run byte for byte. Full text: DIAGNOSIS.md.

## Changes per fix
1. Format: `litellm==1.105.0` pinned in tests/Dockerfile; judge `mode = "batched"`; grader stages a 0644 copy of solver.py in a 0755 dir, runs it via setpriv as nobody in its own session under a file lock, kills its process group and leftover nobody processes. `chmod 755 /logs/verifier` kept in test.sh.
2. QC v2 recheck: F1, F2, F3, F8 already fixed at HEAD; F4 fixed (handbook s5 and s14 "no live row in the item status register"); F5, F9-F15, M1-M3 fixed by the rewrite; F6/F7 defended (QC_DEFENCE.md, the chain is deliberate); W1 fixed (delta sign sentence), W2 fixed (instruction forbids starting other programs), W3 fixed (staged copy), W4 fixed (forge 1/101).
3. Hardness: grading moved to four hidden sets (overlays over embedded `_SHIPPED_DATA`, reseeded figures in 16 registers, appended rows, refreshed manifest counts), parsed comparison, seven groups per set. Data: per item `setup_fallback_cents` in runbook `item_defaults` (K14 41000, K22 omitted), handbook s7 fallback rule, s10 tie order. Oracle reads `item_defaults`. Instruction cut to the end state without trap topics, rule counts or an executable-bit demand.
4. Judge: 8 criteria, five shipped-run figures needing the whole chain (446527364, 19229000, 31756967, 75 lots, 33012 units), integer-cents code criterion, honesty negative, /app/data negative. Weights 0.5/101 and 0.5/18.
5. DESIGN.md (Harden round 1), LEVERS.md, TRUTH.md (Verification rewritten, Defect 9 and 10, fixture sha256s), QC_DEFENCE.md, XREF.md.

## Levers before / after
| lever | family | v0 | r1 (v0 solver replay) |
|---|---|---|---|
| V0-01..V0-17 | A/B | LEAKED | still graded through hidden sets |
| LV-EF-L7 K13 lot tie | A | HELD | folded into LV-DPR-01 |
| LV-DPR-01 lot tie order, 2 constructed ties per set | A | new | HELD |
| LV-DPR-02 per item setup fallback, control default decoy, K22 by omission | B | new | HELD |
| LV-DPR-03 first live amendment copy, voided first copy via log | C | new | LEAKED |
| LV-DPR-04 rejection reasons and void accounting | F | new | LEAKED |

## Counts and shares
Tests: 35 criteria (29 positive, P 101; 6 negative, -22). Judge: 8 criteria (P 18, -8). Isolated groups 28/101 = 27.7%. Shipped-run checks 1/101 = 1.0%.
Local (stub rewardkit): oracle 1.0, v0 agent solver 17/101 = 0.168, nop 0, forge 1/101 = 0.0099; mutants m_fallback 0.366, m_tie 0.317, m_amend 0.168, m_rejnorm 0.683, m_voidlog 0.881.

## Gate results (run once)
- QC scripts at HEAD 3fb1650b: structure_qc 17 pass / 1 warn (X1 binary files) / 0 fail; instruction_qc 5/0/0; tests_qc 36/0/0 (K8, H6, O1 0% overlap pass); judge_qc 19/0/0.
- validate_bundle.py (advisory): 42 pass, 7 fail (§1.12 archetype manifest, §6.1 solve.sh copy, §7.2 seed constant names, §11.2-11.5 recommended negatives); left as is, see QC_DEFENCE.md.
- xref_check: 18 entries, 0 findings.
- Docker, tests-only exe_copy copies (`/tmp/opencode-logs/dpr-gates-20261022T225208-2178/jobs`): oracle-1 1.0, oracle-2 1.0, owner-only-1 1.0, oracle-0600-1 (solve.sh + `chmod 600 /app/out/solver.py`) 1.0, nop-1 0.0. No exception files.
- Forgery: 1/101 = 0.0099 (local, solver that copies the shipped gold).

## Not run
- Judge channel not executed (validated by exe_copy schema load and by reading). No agent trajectory on r1. Forgery not run in Docker. TRUTH.md edited (one wording fix, sha256 refresh) after the exe_copy copies were made; no graded file changed.

## QL coverage (Input_Bundle_QC changes since 2690e960)
| change | where | status |
|---|---|---|
| TS-2 / TS-S11 / tests_qc K8 litellm exact pin 1.105.0 | 03_Tests_QC.md, tests_qc.py | FIXED (pin added, K8 pass) |
| TS-30 / TS-S16 / tests_qc H6 program readable before uid drop | 03_Tests_QC.md, tests_qc.py | FIXED (staged 0644 copy, chmod in the setpriv function) |
| H6 interpreter switches parsing | tests_qc.py | PASS |
| Step 10 owner-only oracle run (`exe_copy.py --owner-only`) | Final_checklist.md, exe_copy.py | PASS (1.0) |
| exe_copy flag parsing (--stub, --owner-only) | exe_copy.py | PASS (copies built) |
| judge_qc G2 `mode = "batched"` | judge_qc.py | FIXED |
| structure_qc T14 author relaxation | structure_qc.py | PASS |
