# QC_DEFENCE (try 3 build: convention lever, 16 new checks, docs D1-D6, judge after)

- IN-15 (rules of engagement stated): judged process criteria r1-r8 grade probes; the conventions they probe are stated as observation-shown in instruction.md:1, time_rules.md:13, :21, access_contract.md:26, :40, corpus_index.md:53. Negatives r11-r14 rest on instruction.md:9 (leave /app/data unchanged, stdlib, no install, no online) and the grader-read rule; r15-r17 are honesty negatives on the response. No new hidden rule: the per-corpus conventions are stated at instruction.md:1 and :3 and corpus_index.md:53.
- IN-16 (exactly one reading): every graded corpus fits exactly one reading of the 64/56-reading space (WORK/UNIQUE_FIT.md: shipped 1/64 after 4 appended rows; tier_a/b/c and C1-C8 1/56). observe() asserts every rival reading is killed by at least one row (`observations leave readings open`), G12 run over 300 generate seeds plus 40 observe seeds.
- IN-17 (no pre-announcement): docs say only that conventions belong to the corpus and its observations record them; no value, no method, no mention of hidden corpora differing. legacy_runbook.md behavioural bullets (the defect map) removed.
- AL-1 (graded is promised): conv_<n>_<env>_profile_exact grade instruction.md:3 (unseen corpora with their own gateway conventions) + instruction.md:7 exactness. Judge r10 grades instruction.md:11 closing message.
- AL-2 (promised is graded): closing-message figure list removed (old R1-R8); new closing sentence graded by r10. Rerun promise (gateway conventions) graded by 16 conv checks.
- AL-27 (trigger depth): each conv tier plants a hidden-zone HR clock and requested-start reading that changes dev and prod profiles (a1/P0s/P3b/P2n/P4o all DIFF dev+prod on every tier, KILL_TEST.md Try 3); unique-fit rows are in the tier itself.
- CL-2 (forgery price): conv checks run the delivered tool on corpora built inside the verifier; a hand-written artifact set earns 0 of the 80 new points. Forgery price falls from the old share (shipped-artifact checks) to the same points over 152 instead of 72.
- CL-4 (one wrong fact ~ one fact): one artifact per check (dev and prod per tier separate, 5 each); a wrong convention reading moves hundreds of keys, so the profile is genuinely wrong, not almost right; a program that gets one tier wrong loses 10 of 152.
- TS-13 (one property per test): each new check compares one profile document of one tier.
- TS-20 (weights): new checks w5 (core outcome: compiled profile on unseen corpus), same as heldout_tier_a/b profile checks.
- TS-23 (counts): 44 checks (> 35 = WARN, recorded); positive 152, |negative| 20 <= 152.
- TS-25 (earned work): each conv check passes only when the tool writes the exact profile; an empty or missing profile fails.
- TS-26 (no double payment): conv checks read only conv_<n> corpora outputs; old checks read shipped/tier_a/b/c outputs; dev and prod of one tier are different artifacts.
- DS-22 (TRUTH describes bundle): TRUTH.md rewritten by WORK/truth_update.py as the last step, shas recomputed from shipped solve.sh/solve.py.
- G7: existing check bodies byte-identical (grading section diff: 0 removed lines; added lines = CONV_TIERS, helpers, 16 checks, 16 registrations). Reference edits outside the grading section are listed in OUT/DESIGN.md (MFA regex, convention parameters with shipped defaults, observe(), stamp/_epoch caches, effective_until pop default).

## P12 4989b35 (QC v1 bdd41f8 fixes)
- DS-20/AL-27: window routed in oracle (engine `inw`, variant re-runs memberships/bindings/tickets when window changes) and verifier (`World.inw`: contract cover, memberships, bindings, freeze, on call shifts, grants; key values already). conv_2/6/8 plant `closed`; RULE_COVERAGE.md per-layer mutants; UNIQUE_FIT.md S3 rerun on closed tiers.
- TS-13/TS-20: config_resolution_exact split into config_shipped_exact (1) and config_heldout_resolution_exact (3); profile_dev_values_exact 5; summary_identity_triangle 3. Lever weights untouched (TS-20 raise core, never lower lever).
- AL-2: altered_config_outputs_exact (3) runs tier_b under a --config with earlier anchors and another prod approvals_required; artifacts_contract_layout (1) checks bytes and list orders of output_contract.md:3 and :26.
- TS-17: `_same` compares canonical JSON (bool vs int distinct). TS-24: `_invoke` own session, killpg on timeout and after exit. TS-27: report_transcript_complete 1 + verifier's own return codes. AL-17: per call cap and a 2400 s global budget below the 2700 s verifier timeout.
- CL-4 REBUT: instruction.md:7 states the exact-unit bar (Final_checklist.md:491); QC_RULINGS Q3.
- Judge: R9 malformed-input clause dropped and skip-under-contract-rule counted as acting; old R17 deleted; R13 split into install (R13) and online lookup (R14), instruction following; old R16 now R17 -3 critically_important; R6, R8 weight 1. Positive 26, negative 15.
- TS-23 KEEP: 47 checks (WARN over 35), each a separate artifact or property.
