# HARDEN_REPORT: vendor-archive-roundtrip-recovery, P9 harden lp1 r1 (board 52dbb3c)

23 Oct 2026, 08:45 to 09:30 IST. LEVER_PLAN_v1. Live QC kit at harness HEAD 71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e. BUNDLE tree aa49997215a6 (26 files), was f0cfd07a5746 (25 files). All scores are tests-only; the judge was not run (no key).

## Outcome
DONE. The a2 run's 100/100/100 was genuine: its levers were weak by design (OUT/DIAGNOSIS.md). The harden adds four levers: L2, L3, L5 and L6. The real agent's a2 program now scores **0.1682** tests-only on the new tests, at or under the 0.20 gate. Stacking PASS, QC 0 FAIL, xref 0. The Docker gates read oracle 1.0 x3, owner-only 1.0, nop 0.0, stub 0.0 and forgery 0.028.

## Levers, before and after
| | Before (r1, a2 run) | After (lp1 r1) |
|---|---|---|
| Levers | RUN, REV decoy, REMAP, STATE, ESC/EXT, SALV, ENC, REJ: each one plain sentence beside its use, two with the trap explained | L2 count unit unsigned behind the `value_sum` control; L6 cumulator per field name (Terms); L3 run ledger with resends; L5 JSON boolean override / JSON integer length beside trim rules |
| Where each rule is written | contract, appendix and escape_rules, beside use | L2: format_contract.md L152-155 (control L9-12, default L90). L6: format_contract.md L188-190 (use L92-93). L3: decoder_appendix.md L92-105. L5: decoder_appendix.md L106-108 and L72-74, normalisers L86-88 and L79-80, separating row in stream3_manifest.json |
| Shipped data separates the lever | yes (stream 3 showed the run rule) | no, except L5's string override row (W5). Per-field and per-stream cumulators agree on all 15200 clean captures and on stream 3. Both the correct reading and the all-unsigned repair satisfy every `value_sum` |
| a2 agent, tests channel | 100.0 | 16.82 (with its own reports regenerated; 14.02 with its stale /app/out) |
| Judge | 4 shipped figures (20 of 24 points), code quality, method lines, 2 negatives | 4 conduct w3 (one per lever), named-shape code quality w3, catalog round trip w1, honesty -3, grader paths -5 |

## Counts and weight shares
- Tests: 27 positive checks (P = 107) and 5 negatives (-19, cheating only).
  - Whole documents on hidden reseeded inputs: 65 = **60.7%** (target at least 50%).
  - Isolated rule checks (8) plus mutation checks (2): 30 = **28.0%** (at most 30%).
  - Shipped-only: report_format, 3 = **2.8%** (at most 5%).
  - Other report checks: 9 = 8.4%.
  - Core weights are 5 and 3, never 1.
- Judge: 8 criteria, mode "batched". Positives sum to 16 and negatives to 8.
- reward.toml: test_output 0.004672897196261682 (0.5/107), judge 0.03125 (0.5/16).
- Writing: two W1 trap sentences removed from escape_rules.md. The instruction no longer asks for figures and states "Each output document is graded whole on fresh inputs."

## Gates (run once each)
| Gate | Result |
|---|---|
| structure_qc | 17 pass, 1 warn (X1: binary .varc files, as in every round), 0 fail |
| instruction_qc | 5 / 0 / 0 |
| tests_qc | 37 / 0 / 0. B4 failed once, on a message log under /logs/verifier; FIXED by moving messages to stdout |
| judge_qc | 19 / 0 / 0 |
| validate_bundle.py --archetype format-recovery | 49 passed, 0 failed, 0 warnings, GATE PASS |
| playground static | did not run: `playground.py` was removed upstream (a72c20a4) |
| xref_check | 53 entries, 0 findings |
| Stacking (OUT/STACKING_CHECK.md) | PASS |
| Docker (TS 20261023T092536-35fa, one chain, ALL_DONE 09:28:26) | oracle 1.0 / 1.0 / 1.0; owner-only 1.0; nop 0.0; stub 0.0; forgery 0.028; no exceptions |

QL rule, checks changed in `git diff 2690e960 HEAD -- Input_Bundle_QC/`:
- K8 litellm pin: PASS.
- H6 grant read: PASS (FIXED this round by adding `_grant_read` on staged copies).
- TS-30 owner-only: PASS (owner-only run 1.0).
- H6 interpreter switches: PASS.
- G2 batched judge: PASS.
- T14 / FC-S18 author: PASS.
- S3/S5 shipped trajectories/: PASS (none shipped).
- H1, H3, H5, K1, K5, K7, S9, J1, J6: PASS.

## Deviations, and what was not run
- **G7:** messages are not in ctrf. rewardkit 0.2.1 has no message field, harness `scripts/normalize_ctrf.py` strips `message`, and tests_qc B4 fails a test that writes under /logs/verifier. Each failure reason is printed as `[check] <name>: <reason>` to the verifier stdout (test-stdout.txt). The forgery run shows them.
- **Oracle runs:** x3, per Ayush; the kit asks for x5.
- **Judge:** not run (no API key). R1 to R4 are conduct criteria that the oracle cannot meet (JD-7), accepted by Ayush under LEVER_PLAN_v1 J2 (QC_DEFENCE H5).
- **No real trajectory was run.** The 0.1682 is the a2 program's reading, not a fresh agent's. A careful agent that reads Field names, Terms and Runs can code all four rules, and the levers depend on misreading. The single-misreading variants are in STACKING_CHECK section (c).

## Files written
- BUNDLE: instruction.md, environment/data (format_contract.md, decoder_appendix.md, escape_rules.md, regenerated capture_catalog.jsonl / alpha / beta / gamma, new stream3_manifest.json), tests/test_output.py, tests/judge.toml, tests/reward.toml, solution/solve.py, solution/TRUTH.md.
- WORK: DESIGN.md, LEVERS.md, QC_DEFENCE.md (all with a "Harden lp1 r1" section), XREF.md, README_STALE.md, TODO.md, LOG.md, qc/*_lp1r1.txt.
- OUT: DIAGNOSIS.md, STACKING_CHECK.md, HARDEN_REPORT.md, agent_program/, result_52dbb3c.json.

Next step: master issues P11 v2 QC.
