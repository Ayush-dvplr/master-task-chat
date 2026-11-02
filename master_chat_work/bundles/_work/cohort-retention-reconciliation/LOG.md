# LOG (IST)
- 16:05 cp -Rp source -> bundle, exit 0; tree sha ae77ceb8...; job copied as e5d428
- 20:58 P1 done: DIAGNOSIS.md, LEVERS.md v0 table; trap fired, all levers leaked (probe 12/12)

2026-10-22 22:00 IST gates2.sh: oracle x2 1.0, owner-only 1.0, oracle-0600 1.0, nop 0.0, stub 0.0333, forgery 0.0; 0 Permission denied. HARDEN_REPORT section 5 completed.

## P12 r1 (board 0b8ac36)
- 2026-10-22 22:59 IST rename session ok; kit HEAD 3fb1650b; BUNDLE==QC copy
- 23:03 P12 Phase0 done: QC_DEFENCE.md written; XREF.md 20 entries, xref_check 0 findings.
- 23:20 P12 Phase2 edits applied: solve.py rewritten (independent; local grade 20/20 positives pass, byte-identical shipped outputs, O1 16%->2%), test_output.py serialization+deterministic require full doc set + reference cohorts (stub/empty now fail), TRUTH R4 14 + register breakdown + solution shape + plan step 6 + caveat mutation/round-0 sentences removed + solve sha, judge R4 14, R7 -> r7_program_code_quality, task.toml description. xref 25 entries 0 findings; 4 QC scripts PASS 0 fail.
- 23:08 P12 Docker chain launched: log /tmp/opencode-logs/crr-p12-20261022T230841-4feb/runs.log, jobs /tmp/harbor-jobs-p12/crr-20261022T230841-4feb, copies /tmp/p12-crr-20261022T230841-4feb, lock held
- 23:13 P12 Docker ALL_DONE: oracle 1.0 x3, owner 1.0, nop 0.0; lock released; deliverables written (RECHECK_FIX.md, PL_NOTE.md, result_0b8ac36.json tree_sha 8667ff1e386d); P12 DONE
- 2026-10-23 00:53 IST P9 r2 (7cbd9f5) start; session renamed ok
- 2026-10-23 01:00 IST P9 r2 Phase 1 done: OUT/DIAGNOSIS.md written. PRIMARY CAUSE 4 (levers weak by design: every rule one explicit sentence, agent coded all right first write, steps 4-11); cause 1 NO (run copy = BUNDLE 8667ff1e386d + harness staging); cause 2 PARTLY (v0 without trap 87.5, tests 100%); cause 3 NO for agent-visible, PARTLY rubric (R4 13->14 correctness). All CR-1..5, V0-1..8 LEAKED. Waiting for go.

- 08:55 r2 GO-3 done: data/docs/instruction edited (L1 manifest, L2 identifiers, L3 balance, L4 weight_override).
- ~08:58 GO-4 solve.py + GO-5 test_output.py rewritten. Local scorer (/var/folders/.../opencode/r2/score.py, variants.py): oracle 1.0, a2 0.0571, S2 0.0571, S4 0.1619, S3: L1a .83 L1b .86 L2a .24 L2b .38 L2c .21 L2none .21 L3a .70 L3b .73 L4a .70 L4b .75.
- ~09:02 GO-4/5/6 done: TRUTH.md, judge.toml (C1-C4 w3 conduct, C5 w2 code quality, N1 -5), reward.toml 0.5/70 + 0.5/14, OUT/STACKING_CHECK.md a2 0.0571 PASS.
- ~09:06 GO-7 done: LEVERS.md r2 section, DESIGN r2, QC_DEFENCE r2, XREF 33 entries, xref_check 0 findings. Next GO-8 Phase 3.
- 09:08 weights moved to kit scale {1,3,5} (dropped fixtures duplicates_match_identifiers, subtracting_events_draw_on_the_balance), judge R1-R8 (8 criteria, +19); 4 QC scripts PASS 0 FAIL; validate_bundle 44/6 (6 pre-existing, same as r1); local final: oracle 1.0, a2 0.0563, S2 0.0563, S4 0.1690, stub 0.0141. Earlier LOG times corrected (were guessed).
- 09:11 lock taken; TS 20261023T091041-52df; copies plain/owner/stub (exe_copy) + forge; images warmed; chain started (oracle x3, owner, nop, stub, forge), log /tmp/opencode-logs/crr-r2-20261023T091041-52df/runs.log, jobs /tmp/harbor-jobs-r2/crr-20261023T091041-52df.
- 09:15 Docker ALL_DONE: oracle 1.0 x3, owner 1.0, nop 0.0, stub 0.0141, forge -0.0563, n_errors 0, no Permission denied; lock released. 09:18 HARDEN_REPORT.md + result_7cbd9f5.json (DONE, tree 79a3d90c0965), baselines.json round2.
- 10:44 P12 r2 (f6164ef) start: session renamed, rules + v3.md read; kit 71a653b2 unchanged; BUNDLE == QC r3 copy. Findings: JD-7, DS-22, AL-2/CL-1, AL-27 (fail), TS-13, TS-29 (minor).
- 10:52 P0 reflex baseline (local scorer p12r2/score.py on current tests): a2 0.0563 (artifact 1 + spaced 3 = 4/71), oracle 1.0.
- 10:58 P12 r2 P1 labels: JD-7 REAL, DS-22 REAL, AL-2 REAL, AL-27 REAL (mutants m1 resolved-key dup and m2 exclusion-before-dup both 1.0 on old tests), TS-13 REAL minor KEEP, TS-29 REAL minor FIX by TRUTH deviation note.
- 11:05 P2 edits: solve.py strict_day uses calendar.monthrange, no except clause left; instruction.md line 7 (final reply figures) deleted; test_output.py _study_files adds l3/rb same-day purchase pair in [d_c, d_d-1] and a repeated in-calendar barred session row; TRUTH drift item 6, step 6, TS-29 deviation. Local: oracle 1.0, m1 0.7418, m2 0.9296, a2 reflex 0.0563. No-gate probe (TS-13): a2 unchanged 0.0563.
- 10:58 P2 gates: QC scripts 17/5/37/19 pass 0 fail; xref 33 entries 0 findings; stacking PASS (60.6%, 1.4%). Docker (lock taken and released, TS 20261023T105600-904b): oracle 1.000 x3, owner-only 1.000, nop 0.000, ALL_DONE.
- 11:00 Deliverables written in p12_r2: RECHECK_FIX.md, PL_NOTE.md, STACKING_CHECK.md, result_f6164ef.json (DONE, tree_sha 876a81556710).
- 11:30 P12 r2 trap-survival follow-up (P12_r2_trap.md): old tests from QC r3 copy (sha1 7014901c, diff = AL-27 lines only); 10 S3 variants from harden_r2 variants.py on current solve.py; losses of 71 before->after L1a 11->11 L1b 8->8 L2none 54->55 L2a 54->53 (0.981) L2b 38->38 L2c 53->53 L3a 18->18 L3b 18->18 L4a 21->21 L4b 16.33->16.33; reflex 0.0563->0.0563; oracle 1.0 both. PASS, no bundle change, no Docker. RECHECK_FIX ## Trap survival + result json trap_survival/lever_loss written. Logs p12_r2/gates/trap_survival/.
- 2026-10-23 12:19 IST P12 r3 (cac63fd) start; session renamed ok
- 12:22 P0 xref_check 33 entries 0 findings; reflex a2 baseline 0.0563 (4/71) on current tests. Trap before (WORK/trap/ read-only copy): loss of 71 L1a 11, L1b 8, L2a 53, L2b 38, L2c 53, L2none 55, L3a 18, L3b 18, L4a 21, L4b 16.33; oracle 1.0. AL-27 mutation run (QC mut.py copy, p12_r3/gates/al27) started on before copy.
- 12:40 AL-27 side rows in _study_files (side Rng), IN-16 schema.md:41 tie sentence + hidden tie row, re-embedded _SHIPPED_DATA. Mutants after (of 71): date-only 56, type-desc 56, zero-rev dropped 66, offset_zero_always 70, control_zero 68, sign flip 68, calendar lexical 45, mismatches manifest order 66, unsorted reversed 66, merge tie earlier row 36.667, rate 0/0 71 (UNSURE), baseline 71. Trap after first try: L1a 11->6 FAIL (forced value fault made L1a control red too); compensation (L1 family): forced fault = minus the padded-value total so manifest agrees with unstripped reading. Trap after: all ratios >= 0.981, separating checks kept, reflex 0.0563, oracle 1.0. PASS.
- 12:39 P12 r3: TRUTH prose, LEVERS, QC_DEFENCE updated; DS-22 solve.py bf91bc6f..., 552 lines recorded last; xref 0, QC scripts 0 FAIL, stacking PASS, reflex 0.0563 -> 0.0563, trap PASS (L1a compensated 11->6->11).
- 12:39 P12 r3 Docker (tests only): oracle 1,1,1 owner 1 nop 0, ALL_DONE; lock released. Deliverables written in p12_r3 (RECHECK_FIX, PL_NOTE, STACKING_CHECK, result_cac63fd.json, tree 49de03208255). Status DONE; AL-27(e) UNSURE to PL.
