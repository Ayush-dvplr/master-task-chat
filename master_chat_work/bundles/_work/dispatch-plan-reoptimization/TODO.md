# TODO eedf614 dispatch-plan-reoptimization harden r1
- [x] P0 session rename, HEAD 3fb1650b, copy bundle, copy job, baselines.json
- [x] P1 diagnosis: trap, levers, composition, DIAGNOSIS.md
- [x] P2.1 format fixes (K8 pin, _grant_read + kill by uid/pgid serialised, judge batched)
- [x] P2.2 QC v2 FAIL/WARN recheck
- [x] P2.3 hardness redesign (data/instruction/tests/solve)
- [x] P2.4 judge rewrite
- [x] P2.5 DESIGN/LEVERS/TRUTH/rule 6, QC_DEFENCE, XREF
- [x] P3 gates (QC x4, validator, xref, docker oracle x2/owner/0600/nop, forgery)
- [x] HARDEN_REPORT.md, result_eedf614.json, final reply

# TODO eb5e097 P12 r1 (QC v1 fix), started 22 Oct 23:30 IST
- [x] P0 rename (ses_e9b3a8b83ffe02Giu2kHV3fFdO shown as eb5e097), kit HEAD 3fb1650b, QC_DEFENCE/XREF exist, xref 0 findings
- [x] P1 recheck F1 IN-15/TS-16, F2 TS-17, F3 JD-18, F4 CL-5/TS-19, M5 DS-5, M6 DS-22, M7 JD-2, W8 TS-24, W9 X1 -> OUT/RECHECK_FIX.md
- [x] P2.1 apply fixes (bundle), keep TRUTH/LEVERS/QC_DEFENCE/XREF in step, rule 6 if data edit
- [x] P2.2 xref 0, 4 QC scripts 0 FAIL, manual checks
- [x] P2.3 warm image, Docker chain oracle x3 / owner x1 / nop x1 (ALL_DONE)
- [x] P3 RECHECK_FIX gates, PL_NOTE.md, result_eb5e097.json

# TODO eec3fbe P12 r2 (QC v2 fix: IN-15, JD-7, AL-28), started 23 Oct 00:33 IST
- [x] P0 rename (ses_e9b013b46ffeJvwKytB2XO7xdc shown as eec3fbe), read rules
- [x] P0 kit HEAD, QC_DEFENCE/XREF exist, xref 0 findings
- [x] P1 recheck every finding of v2.md -> OUT/RECHECK_FIX.md
- [x] P2.1 apply fixes, keep TRUTH/LEVERS/QC_DEFENCE/XREF in step
- [x] P2.2 xref 0, 4 QC scripts 0 FAIL, manual checks
- [x] P2.3 warm image, Docker chain oracle x3 / owner x1 / nop x1 (if tests/solution/env changed)
- [x] P3 RECHECK_FIX gates, PL_NOTE.md, result_eec3fbe.json

# TODO 27b6cc2 P12 r3, 23 Oct 2026
- [x] P0 rename, rules, fingerprint, HEAD, xref, before copy
- [x] P0 local before scores and generator drift check
- [x] P1 recheck v3 findings and report rows
- [x] P2 fixes in generator, rebuild, judge, TRUTH and notes
- [x] P2 probes, xref, QC, stacking, after scores
- [x] P2 Docker chain oracle x3, owner x1, nop x1
- [x] P3 deliverables, lock release, final rename

# TODO cc4bb7f P12 judge r1 (judge rework from a2), 23 Oct 2026
- [x] P0 rename, rules read, fingerprints, HEAD 71a653b2, kit judge rules, a2 old score 18/21 reproduced
- [x] P1 oracle figures recomputed (solve.py in temp APP_ROOT), diff vs a2 artifacts
- [x] P2 Phase A paper judge (a2 old/new, reference new), targets
- [x] P3 Phase B: lock, edit tests/judge.toml, WORK notes, xref, judge_qc, stacking, hashes
- [x] P4 deliverables JUDGE_REWORK.md, PL_NOTE.md, result_cc4bb7f.json, lock release, rename

# TODO 77e8554 P12 v3 r1 (QC v6 2966bb2 fix), 24 Oct 2026. Prompt: master_chat_tasks/prompts/issued/dispatch-plan-reoptimization/20261024T1142_fix.md
- [x] P0a rename (opencode ses_e9362dc6fffe503H8KGFkEv9iv), tree d2abee833b88 ok, kit HEAD 71a653b2, fingerprints match
- [x] P0b xref_check 0 findings (baseline)
- [x] P0c lock taken; copy tests/ solution/ environment/ to WORK/trap/before_v3/
- [x] P0d trap baseline: a2 solver + variants (list) on BEFORE tests, local scorer
- [x] P1 recheck F1 DS-22, F2 TS-16, F3 JD-8, M1 TS-15, M2 JD-7, M3 JD-13, M4 JD-5, W1 DS-20, W2 TS-14, W3 TS-23 -> OUT/RECHECK_FIX.md
- [x] P2.1 generator diff (Always 11): mktests.py output == bundle test_output.py byte for byte, cases.json same
- [x] P2.2 fixes: M2+W1 solve.py (byte-identical proof), F2 TS-16 (+WORK/wrong probes), M1, W2 rename, W3 merge, F3/M4 judge, F1 TRUTH last
- [x] P2.3 XREF update + xref 0; manual checks per ID + side effects; precheck CLEAN
- [x] P2.4 stacking_check -> OUT/STACKING_CHECK.md
- [x] P2.5 trap survival after (all variants ratio 1.00; ts16_cheat_tmp fires -3; ts16_honest clean locally)
- [x] P2.6 warm verifier, Docker chain oracle x3/owner/nop/stub/ts16-honest (ALL_DONE)
- [x] P3 RECHECK_FIX, PL_NOTE, result_77e8554.json, lock release, rename

# TODO 6cd567a P12 v3 r2 (QC v6 c2cde12 fix), 24 Oct 2026. OUT: master_chat_work/20261022_dispatch-plan-reoptimization/p12_v3_r2
- [x] P0a rename (opencode ses_e9304e5a8ffeJEMuhgyE1GmWOQ), tree cc3a0ebba1cb ok, kit HEAD 71a653b2, lock taken 13:47
- [x] P0b xref_check 0 findings (baseline)
- [x] P0c copy tests/ solution/ environment/ to WORK/trap/before_v3r2/
- [x] P0d trap baseline: a2 solver + variants + M10/M11/M16 on BEFORE tests
- [x] P1 recheck F1 DS-20, F2 DS-22, F3 JD-8, F4 AL-27, M1 JD-15/16, W1 X1, W2 IN-16, W3 TS-16 -> OUT/RECHECK_FIX.md
- [x] P2.1 generator diff (Always 11): rebuild to scratch, tests/db/cases byte-identical
- [x] P2.2 fixes F1 handbook, W2 handbook, M1/F3 judge, W3 tests, F4 overlays+goldens, F2 TRUTH last
- [x] P2.3 XREF + xref 0; manual checks + side effects; precheck CLEAN; structure_qc
- [x] P2.4 stacking_check -> OUT/STACKING_CHECK.md
- [x] P2.5 trap survival after + M10/M11/M16 after + TS-16 programs
- [x] P2.6 warm verifier, Docker chain oracle x3/owner/nop/stub/ts16-honest (ALL_DONE)
- [x] P3 RECHECK_FIX, PL_NOTE, result_6cd567a.json, lock release, rename

# TODO 2c2361c P12 v3 r3 (QC v7 fix: AL-28, IN-16, X1, TS-14), 24 Oct 2026
- [x] P0 rename (ses_e928b884affesfSeGcTKs5LKh5), tree 1341a5ab938f ok, HEAD 976c1666, fingerprints 0 diffs, lock taken
- [x] P0.1 xref_check 0 findings (41 entries)
- [x] P0.2 copy tests/solution/environment to trap/before_v3r3; baseline scores (a2, agent_v0, m_*, M10/M11/M16, ts16_*)
- [x] P1 recheck F1 AL-28, M1 IN-16, W1 X1, W2 TS-14 -> OUT/RECHECK_FIX.md
- [x] P2.1 generator diff (Always 11)
- [x] P2.2 F1 hook fix (mktests.py source + regenerate) + decide temp-write side
- [x] P2.3 M1 instruction.md:3 sentence
- [x] P2.4 W2 dead defs removed; identical-results proof
- [x] P2.5 AL-28 programs in WORK/wrong; after scores; trap survival
- [x] P2.6 QC_DEFENCE/LEVERS/XREF/TRUTH last; xref 0; precheck CLEAN; structure_qc 0; stacking
- [x] P2.7 Docker chain (warm, oracle x3, owner, nop, stub, honest, scratch) ALL_DONE
- [x] P3 deliverables RECHECK_FIX, PL_NOTE, result json; lock release; final rename
