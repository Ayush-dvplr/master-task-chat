# QC risks in the original bytes (tree 4c85938aa8d4), with their status after build try 3 (30 Oct)

1. Answer key contradicts the contract (blocker). tests/test_output.py:46, :157 drop `idp_mfa_events.log` lines whose
   `<at>` has a space instead of `T`; time_rules.md:5 requires `bad_timestamp` and output_contract.md:26 counts every
   line in `records`. All 21 lost a1 points come from this. Fix: classify a non-matching non-comment line as a record and
   reject it `bad_timestamp`. After the fix the a1 program scores 72/72.
2. Defect map in the environment (leak). legacy_runbook.md:3 says the first release "was built to match it"; its 2024
   bullets list the planted defects one by one (a1 step 70: "each of its bullets was a defect").
3. Latent reference bounds against an unbounded rule (access_contract.md:28): `shifts()` looks back only 9 days for the
   shift in effect (test_output.py:919) and carries at most 800 shifts (:933). No current corpus reaches them.
4. Reference crashes on a UTF-8 BOM (`KeyError '\ufeffevent_id'` in hr_layer); docs are silent on BOMs. Not planted.
5. Generator cannot scale: heldout scale 5 fails `random.sample` (test_output.py:1297), heldout scale 2 fails
   `KeyError 'effective_until'` (:2229). Fine for current tiers; blocks any size lever.
6. Test file is 3.0 MB / 30,046 lines because SHIPPED_CORPUS is embedded as zlib+base64 (lines 2683-29441).
7. Judge: R1-R8 are figure criteria worth 40 of 73 positive points (J1 forbids figure criteria); R17 is a
   self-consistency criterion; R18 bundles two properties ("repairs stay in modules"), JD-5 risk.
8. (found in try 3) Shipped observations fit two grant start readings: k-th qualifying decided_at and the instant the
   k-th distinct qualifying approval was recorded (unique-fit 2/48, WORK/UNIQUE_FIT.md; a1 trajectory step 38 also
   fit all 2195 accepted rows with latest decided_at). Outputs differ (dev 135, prod 231 units), so instruction.md:1
   "exactly one reading ... reproduces every observation" is false on shipped data. Fix needs shipped rows (master's call).
   RESOLVED in build (master ruling 2): measured in Docker (WORK/proto/t3/risk8.txt): shipped profiles differ under
   start=latest (dev 117, prod 124 units) and start=recorded (dev 135, prod 231 units), summary differs. Shipped data
   changed: 4 dev keep rows AT-002250..AT-002253 appended to access_attestations.csv (observe() stream seed 0,
   old 2249 rows byte-identical). Reference profiles unchanged; self_check counts +4. Unique fit on new shipped:
   1/64 site/decided/half (WORK/proto/t4/uniq_ship.txt, 272 s). a1 program and oracle keep every old shipped check.

## Status after build try 3 (master option 1: fix risks 1, 2 and 7)
- 1 FIXED: the reference reads every non-comment idp_mfa_events.log line as a record (tests/test_output.py:48 MFARX
  `(.+?) (\S+) ...`, :171) and rejects a bad instant `bad_timestamp`; the oracle carries the same repair.
- 2 FIXED: legacy_runbook.md cut to 9 lines with no defect list (WORK/DOC_DIFFS.md D5).
- 3, 4 and 6 OPEN: original bytes, not touched by the build.
- 5 PARTLY: the generator `row.pop("effective_until")` KeyError became `pop(..., None)` (needed for the 300 seed G12
  run; no RNG change, outputs identical where it ran). The scale 5 `random.sample` bound remains (no size lever used).
- 7 FIXED: judge rewritten to 17 binary single-property criteria, no figure criterion (WORK/JUDGE_MAP.md).
- 8 RESOLVED as above (shipped data changed).
- 9 (validator, Phase 3) validate_bundle.py section 7.4 wants a registered negative test named
  `negative_hardcoded_sample_answers`. The bundle covers the same act as `negative_tool_ignores_input` (-5,
  tests/test_output.py:30123, comment "Fires on a tool that hardcodes answers instead of reading --data."). The a1
  backup fails 7.4 the same way, so it is pre-existing. Not changed: a rename breaks old-check byte identity (G7) and a
  second check stacks one act (AL-28) on a design the master said not to grow. Validator vs old-check rule conflict is
  for the master and Ayush (decision D1, 21 Oct).
- 10 (validator 15.5, QC DS-27) TRUTH.md provenance carried `status: ready`; removed by WORK/truth_update.py.
- 11 (QC CL-2 watch, harbor forgery-1) Real artifacts plus the unrepaired shipped tool.zip score 0.3026 = 46/152.
  The 13 original artifact-only checks on the shipped corpus pay 47 (profile_prod_keys_exact 5,
  profile_prod_values_exact 5, profile_dev_keys_exact 5, audit_rejects_exact 5, summary_identity_triangle 5,
  profile_dev_values_exact 3, audit_unresolved_exact 3, audit_held_grants_exact 3, audit_unattested_exact 3,
  audit_sod_exact 3, self_check_partition_exact 3, report_transcript_complete 3, artifacts_parse_with_contract_shapes
  1), less negative_legacy_tool_delivered (-1). Every check that reruns the tool (held-out tiers, conv tiers,
  artifacts_reproduce_from_tool) pays 0. Those 13 checks were 47 of 72 positive points (65%) before the build and are
  47 of 152 (31%) now. Original bytes, not changed (G7; master "do not add more"). Similar shares were flagged as
  "high (QC CL-2 may flag)" on earlier tasks (metered 0.2555; district 0.2489 and 0.341).
