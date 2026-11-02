# TODO 6740572 warrant-asof-entitlement-compiler (harden-g37-a1)

## Phase 0
- [x] session rename (opencode ses_e7732674affeJ9iNIiv4AmJz8S listed), rule files read, tree sha 4c85938aa8d4, kit HEAD 5574d77e
- [x] unzip a1 tool.zip -> WORK/a1_program/
- [x] read tests/test_output.py structure (checks, weights, held-out generators, seeds)
- [x] read judge.toml + reward-details + a1 trajectory -> per criterion cheap/real
- [x] diff a1 lost tests vs reference -> OUT/TRIP.md
- [x] OUT/QC_RISKS.md (original bytes)

## Phase 1
- [x] arithmetic
- [x] design new held-out checks + judge probe band
- [x] proto corpora WORK/proto/ + kill programs
- [x] kill test in Docker -> WORK/KILL_TEST.md
- [x] grade a1 trajectory vs new judge
- [x] OUT/DESIGN.md -> STOP "DESIGN READY"
- [x] STOPPED: NO CORE (2 tries measured); blinds and judge regrade not done (moot)

## Phase 1b: option 1 convention lever (design try 3; master 30 Oct 00:10; docs MAY change)
- [x] map reference conventions (HR clock, window boundary, grant start) + observation encoding
- [x] parameterise reference World + generator in WORK copy (proto_ref/make.py; conv variant; observe own RNG seed*13+7)
- [x] MFA space fix (test_output.py:46,:157) before/after per old check (proto/t3/mfa_after.txt: a1 shipped audit+self_check exact)
- [x] unique-fit brute force over planted parameter sets -> WORK/UNIQUE_FIT.md
- [x] doc diffs (corpus_index.md:53, instruction.md:3, legacy_runbook.md:3, others) drafted in WORK (DOC_DIFFS.md)
- [x] judge redesign (drop R1-R8, probe band incl. convention probes + R9-R11,R16; J3; J4; R17/R18 single-property)
- [x] kill programs: a1, P0s, P3b, P2n, P4o, P2w (WORK/kill/)
- [x] kill test Docker -> WORK/KILL_TEST.md (try 3 section)
- [x] unique fit on shipped + old tiers (62029 heldout, 73031 boundary) with new observe
- [x] per-tier seconds + verifier worst case
- [x] OUT/DESIGN.md `## Try 3` section at top; result json step harden-g37-a1-opt1; STOP

## Phase 2: build try 3 (master "go" 30 Oct ~02:25; step harden-g37-a1-opt1-build)
- [x] risk 8: measure shipped outputs under start decided/recorded/latest (Docker) -> decide shipped rows (differ -> 4 dev rows appended, WORK/shipped_new)
- [x] tests/test_output.py: apply make.py edits (MFA, conv, observe, speed) + conv tiers C1-C8 + 16 checks w5 (old bodies byte-identical, digest)
- [x] shipped rows appended if risk 8 needs it (env data + SHIPPED_CORPUS consistent), unique fit shipped 1/N
- [x] docs D1-D6 applied
- [x] judge.toml after (17 criteria, 30 positive); reward.toml weights 0.5/152, 0.5/30
- [x] solution: oracle tool with MFA fix + convention inference (shipped call <= 120 s; solve5 max 110.5 s, total 614.7 s, rc 0)
- [x] generator asserts + 300 seeds (generate shape) + branch plant (g12d: G12 OK, 300 generate + 40 observe seeds, kills min >= 1)
- [x] WORK/LEVERS.md, COST_TABLE.md, QC_DEFENCE.md, JUDGE_MAP.md
- [x] TRUTH.md by script last; XREF.md + xref_check 0 (truth_update 8c2a1ed5e517, gateway.py named in step 4; xref2: 14 entries, 0 findings)
- [x] WORK/BLIND_BRIEF.md
## Phase 3
- [x] stacking_check -> OUT/STACKING_CHECK.md (rc 0; AL-28 fixed: R12 -1, R16 -1; acts named by hand)
- [x] measured COST_TABLE on final tests (a1,P2n,P0s,P3b,P4o,P6o) + verifier worst case (P6o 991.5 s, P4o 970.6 s checks)
- [x] precheck CLEAN; 4 QC scripts + validator 0 FAIL (precheck3 PRECHECK CLEAN, 0 IN17/G5 warns; 4 QC exit 0; validator2 39 pass 1 FAIL: 7.4 negative_hardcoded_sample_answers, pre-existing on a1 backup, reported not fixed per D1; xref3 0)
- [x] harbor block: oracle x3, owner-only, nop, stub, forgery (ALL_DONE 05:59:21; oracle 1.0/1.0/1.0, owner 1.0, nop 0.0, stub 0.0, forgery 0.3026; harbor verifier max 740.2 s; WORK/gate/gates.json)
- [x] sync Tasks_INPUT, diff -rq empty, tree shas (10 files cp -Rp 06:02; diff -rq empty; BUNDLE = Tasks_INPUT = 95232d923d75)
- [x] HARDEN_REPORT.md + result json (DONE|PAUSED) (STATUS DONE; json parses, 40 keys; QC_RISKS item 11 forgery; no placeholders, no em/en dashes)

## P12 fix 4989b35 (prompt 20261030T0845_fix.md; OUT p12_fix_v1_4989b35)
- [x] rename session (08:44; opencode listed ses_e75335003ffe59clP1yM6a25oJ)
- [x] read 5 rule files in full
- [x] backup BUNDLE -> WORK/qc1_95232d923d75 (tree 95232d923d75); kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271
- [x] Phase 0: QC_DEFENCE/XREF exist; xref_check 14 entries 0 findings; trap baseline H 80 S 80 W 0 (from KILL_TEST)
- [x] Phase 1 (09:16 table in OUT/RECHECK_FIX.md): read QC report v1 findings + gate sections; recheck each (kit quote, evidence, noise diff vs bdd41f8) -> OUT/RECHECK_FIX.md rows
- [x] F1 G01 task.toml category -> Software Engineering
- [x] F2 (09:40 bundle: tests=p12/t4, solve=solve_new; UNIQUE_FIT P12; RULE_COVERAGE) G02 DS-20/AL-27 window routing solve.py + verifier; replant >=2 conv tiers window closed; UNIQUE_FIT; RULE_COVERAGE.md
- [x] F3 (truth_p12.py run) G02 DS-27 TRUTH.md:55 wording (truth_update.py)
- [x] F4 (t4 _same) G03 TS-17 json.dumps sort_keys compare
- [x] F5 G04 JD-7/AL-4/AL-6 R9 rewrite
- [x] F6 G04 JD-14 delete R17; JD-16 split R13; JD-13 R16 -3 crit; JD-15 R6/R8 -> 1; renumber
- [x] F7 (REBUT, instruction.md:7 + FC:491) G05 CL-4 measure partial credit (rewardkit API) -> fix or rebut
- [x] F8 (altered_config_outputs_exact w2, artifacts_contract_layout w1) G05 AL-2 config-variant check w2 + byte-format/order check w1
- [x] F9 G03 TS-13/TS-20 split config_resolution_exact; profile_dev 3->5; triangle 5->3
- [x] F10 G03 TS-24 _invoke process group kill
- [x] F11 G03 TS-27 report_transcript_complete w1 + rc cross-check
- [x] F12 (450 s = 4 x 111.6 s; budget 2400) G05 AL-17 per-call timeout 120 s (measure) + global deadline
- [x] (reward 0.5/154, 0.5/26; xref 19 entries 0 findings) reward.toml / JUDGE_MAP / LEVERS / QC_DEFENCE / XREF in step; TRUTH by script last
- [x] Phase 2 (precheck CLEAN, stacking PASS, trap survival PASS, vacuity PASS): touched rules, vacuity probe, side effects, precheck CLEAN, stacking, trap survival + rescoring (a1, blinds, kill)
- [x] Docker (gate4 ALL_DONE 13:42: oracle 1.0 x3, owner 1.0, nop 0.0, stub 0.0, forgery 0.2903): warm image; oracle x3/owner/nop
- [x] sync Tasks_INPUT (rsync -a --delete, diff empty, both bd90fad58ff0); deliverables RECHECK_FIX, PL_NOTE, KEPT, result json

## P12 fix d872b22 (prompt 20261030T1600_fix.md; OUT p12_fix_v2_d872b22)
- [x] rename session (opencode listed ses_e73acab7bffeESbABiwJ2sGaWI)
- [x] read rule files; kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271; QC v2 findings read
- [x] backup BUNDLE -> WORK/qc2_bd90fad58ff0; Phase 0 files exist; xref 0
- [x] Phase 0 trap baseline (from previous P12: H80 S80 W30; tests unchanged since)
- [x] Phase 1 recheck rows -> OUT/RECHECK_FIX.md
- [x] F1 AL-2 report_transcript_complete digests + order; digest_mismatch double charge check
- [x] F2 AL-28 partial_output stand down when tier_a==tier_b prod
- [x] F3 TS-13 triangle -> _same only
- [x] F4 TS-29 contract_layout guard
- [x] TRUTH by script (unchanged); precheck CLEAN; xref 0; stacking run
- [x] touched rules; vacuity (-1/155, 0 positives); side effects (written into RECHECK_FIX)
- [x] re-score a1 + kill rows (before/after), trap survival: running p12v2/runs/r1.sh (TS 20261030T160024-a92b, log r1.log, wait ALL_DONE; lock taken)
- [x] Docker: warm image; oracle x3 / owner / nop
- [x] sync Tasks_INPUT; deliverables RECHECK_FIX, PL_NOTE, KEPT, result json
