# HARDEN_REPORT sensor-network-lsq-correlated-adjustment, harden r1 (board baafa14)

Bundle (edited copy): `master_chat_work/bundles/sensor-network-lsq-correlated-adjustment/`
Work notes: `master_chat_work/bundles/_work/sensor-network-lsq-correlated-adjustment/`
Harness HEAD 3fb1650b3b47. Copied tree sha 799669d6..., final tree sha 64f340e2ce43 (67 files).
All scores below are tests-only (no judge key in the Docker gates).

## 1. Diagnosis summary (full text: DIAGNOSIS.md)
- v0 run (claude-opus-5): tests channel 1.0 (24/24, 64/64). The judge did run (22/52), giving reward 0.7115.
- The permission trap did not fire. The holdout re-execution passed. Still, the grader chmodded the agent script in place and depended on Harbor's 0777 `/app/out`.
- Every v0 lever (V0-1..V0-12) LEAKED. The agent solved in one pass in 33 steps. Its run printed `verdict=PASS dof=1019 ...` at 0.9 s.
- What made the levers derivable:
  - The header of every data file had a "Documented traps ... inverse:" block that stated the exact fix.
  - schema.md had `(Trap: ...)` labels and printed the true unit factors.
  - In chi_square_bounds_table.csv the centre was `dof * chi_center`, so the shipped PASS band confirmed the full answer.
  - observation_weight_manifest.csv `apriori_sigma_base` confirmed the unit and sigma conversion row by row.
- v0 score composition: isolated 8/64 = 12.5%, shipped-data-only 54/64 = 84.4%.

## 2. Changes per fix
- 2.1 Format:
  - tests/Dockerfile pip line is now `harbor-rewardkit==0.2.1 litellm==1.105.0` (K8). Its apt line now matches the sibling bundles and adds `getent passwd nobody`.
  - The grader `_grant_read()` copies the program into a grader temp dir (dir 0755, file 0644) and runs it as nobody under setpriv. It holds an fcntl lock, uses `start_new_session` and killpg, and sweeps leftover nobody-uid processes while the lock is held.
  - judge.toml `mode = "batched"`. test.sh is unchanged (`chown root:root` and `chmod 755 /logs/verifier`).
- 2.2 v2.md recheck: I ran live QC at HEAD on the copy before any edits. Only G2 (judge mode) was still open, and it is now fixed. X1 (5 binaries skipped) is a WARN accepted under DS-7. Every other v2 FAIL had already been fixed by fixplan_v2.
- 2.3 Hardness:
  - Removed every answer confirmation: trap/inverse blocks in all files (including `_traps` in JSON/JSONL and the sqlite traps table), schema trap labels and printed factors, the manifest base-sigma column and the decoy_tuning_k label.
  - The acceptance centres are now irregular per row with no formula. The shipped verdict is REJECT_LOW, and no single-miss mutant lands in the PASS band.
  - Added levers H1-H4 (table below) and a third hidden corpus (AUDIT).
  - Grading now covers whole documents on three regenerated hidden extracts.
  - The instruction is now 5 plain paragraphs. It has no rule list, no trap list and no list of what varies. It names schema.md as the authority and asks for four figures in the final reply.
- 2.4 Judge: 8 criteria.
  - Four figures that each need the full chain: vTPv, variance of unit weight, signed residual sum, normal-matrix trace.
  - One code-quality criterion.
  - Negatives: two honesty (figures disagree with artifacts; claims an unrun check) and one boundary (path outside the data or output dirs).
- 2.5 Updated DESIGN.md (Harden round 1), LEVERS.md, TRUTH.md (rewritten; solve.py sha, uuid, fix_patch_sha256, defect labels), QC_DEFENCE.md, PLAN.md, LOG.md. The data is generator-embedded, so rule 6 was met by re-emitting environment/data from `tests/test_output.py` (56 files, deterministic) and updating the TRUTH sha.

## 3. Lever table (before / after)
| id | family | rule | v0 | r1 |
|---|---|---|---|---|
| V0-1..V0-5 units, sigma kind, dir=R, azimuth wrap, transpose | A | shard tokens | LEAKED (trap blocks, inverse text) | kept as conventions; inverse text removed |
| V0-6 workbook controls | A, isolated | u, k, crit, origin | LEAKED | isolated check, 3/62 |
| V0-7/8 IRLS, sessions | A | sec 11, 11b | LEAKED | kept; now fed by H1 variance |
| V0-9/10 blunders, acceptance row | B | sec 12, 14 | LEAKED (PASS band confirmed) | irregular rows, no confirmation |
| V0-11 derived rollups | A | frame/campaign maps | LEAKED (boundary_crosser note) | note removed; graded on hidden maps |
| V0-12 max-abs tie | E | lowest id | LEAKED | kept in residual documents |
| H1-CENTRING (new) | A, split + omission | schema sec 4 + station_registry mount/centring_mm; length only | - | single miss: 8/62 |
| H2-ANGLE-REDUCE (new) | A, decoy default on rare boundary | misclosure into (-200, 200]; 2 shipped straddle rows | - | single miss: 8/62 |
| H3-REVISION (new) | F | duplicate records, higher `revision` wins after un-transposing | - | first-seen: 5/62 |
| H4-CHAIN (new) | B | dedupe -> variance -> IRLS -> blunders -> dof -> acceptance row -> verdict, whole docs on 3 hidden extracts | - | every chain check fails on any single miss |

Mutant scores were measured locally (grade_local, tests-only): no_centring, no_reduce, centring_angles and ignore_mount each score 8/62 = 0.129; first_seen scores 5/62 = 0.081. This is inside the 0.10-0.20 target band for a careful solver with one miss.

## 4. Counts and shares
- Tests: 25 checks (23 positive, P = 62; negatives -5 hardcoded and -3 external dependency, which stand down unless a hidden run was clean). There were 24 checks before.
- Judge: 8 criteria (5 positive, 15 points; negatives -5, -5, -3). There were 21 before.
- Isolated weight 7/62 = 11.3% (control values 3, superseded records 3, canonical 1). Shipped-data-only 1/62 = 1.6% (artifact set).
- reward.toml: test_output 0.008064516129032258 (0.5/62), judge 0.03333333333333333 (0.5/15).

## 5. Gates
- QC x4 at HEAD: structure 17 pass / 1 WARN (X1, DS-7 binaries) / 0 FAIL; instruction 5/0/0; tests 37/0/0; judge 19/0/0.
- QL changed checks (git diff 2690e960..HEAD Input_Bundle_QC):
  - K8 litellm pin: FIXED.
  - H6/TS-30 agent file modes and interpreter switches: PASS.
  - G2 judge mode batched: FIXED.
  - Step 10 owner-only run: PASS (1.0).
  - T14 author name: PASS.
- validate_bundle.py (advisory): 44 pass, 5 FAIL. The FAILs are §1.12 archetype manifest and §11.2-11.5 recommended cheat tests, and all are present in SOURCE as well. §15.4, §15.5 and §15.7 were fixed in TRUTH.md.
- xref_check: 15 entries, 0 findings.
- Hygiene: no em/en dashes, placeholders or CRLF; 2.2 MB.
- Docker (exe_copy copies, logs `/tmp/opencode-logs/snlsq-gates-20261023T001410-865f/`), tests-only:
  - oracle-1 1.0 (62/62)
  - oracle-2 1.0
  - owner-only 1.0
  - oracle-0600 (program chmod 600) 1.0
  - nop 0.0
  - forgery (program replays the shipped reports for any input) -0.0484, which meets the <=0.05 gate. It scored artifact_set 1 and canonical 1, and the hardcoded-answer negative fired.

## 6. Not run
- The judge channel was not run (no OPENAI key in the gates). I checked the 8 criteria by reading them against TRUTH figures and judge_qc.
- No agent trajectory on the hardened bundle yet.
- PL QC, P8 and P7 are not run (Ayush's next steps).
