# KEPT, slipway-overhaul-replan-repair, fix-ql1 481e976

Route 1, Ayush 2 Nov "1. okay". The two warns kept since fix-v1 stay; the QL1
findings below are left as they are on the triage reading (kit HEAD 5574d77e).

| finding | file:line now | kit line it rests on | reason kept |
|---|---|---|---|
| TS-20 (warn) | tests/test_output.py twelve `package_crosswalk_*_exact` registrations, weight 5 each | Input_Bundle_QC/03_Tests_QC.md:51 (TS-20) and :135 (warn is a judgment call) | The crosswalk is the lever: spec_stage_p01_identifier_and_revision.md:19-21 sends every job identifier through identifier_crosswalk.tsv before anything else reads it. It holds 60 of 112 positive points (53.6%), unchanged by this fix. Ayush 1 Nov 17:38: keep. |
| TS-23 (warn) | tests/test_output.py:6088-6137 (50 registrations: 32 positive weighing 112, 18 negative weighing -66) | Input_Bundle_QC/03_Tests_QC.md:62 (TS-23, "at most 35 (warn)") and :135 | Count rose 49 to 50 because QL1-F6 asked for the import scan to move into its own negative. The fail-level parts still hold: 50 >= 10, positives and negatives both exist, weights differ, 66 <= 112. Only the 35 cap warn remains. Ayush 1 Nov 17:38: keep. |
| QL1-F8 (FP) | instruction.md | Input_Bundle_QC/01_Instruction_QC.md:91 | One open compound sentence, not a repeated error pattern; the kit line asks for a pattern before it fails. |
| QL1-F9 (OOS) | environment/data/round_header.json:2 `amendment_window`, written by tests/test_output.py:3555 | DS-6, Input_Bundle_QC/02_Data_QC.md:22 | An unused header field; no kit line makes an unread field a finding. |
| QL1-F12 (KEEP) | tests/judge.toml R6 | JD-5, Input_Bundle_QC/04_Judge_QC.md:71 | R6 holds two facets of one comparison (counters beside the withdrawn rows, the differing stages named): one act, minor. The oracle side is fixed under F5 (solve.sh now prints all three counters of every stage and names every differing stage). |
| QL1-F14 (FP) | environment/data binaries | structure X1 | QL's own check of the 4 binaries came back clean (QC v3:82); X1 stays a warn. |
| QL1-F15 (FP) | tests/test_output.py registrations | TS-23, Input_Bundle_QC/03_Tests_QC.md:62 | The check count is the TS-23 warn Ayush kept (row above). |
| QL1-F16 (FP) | tests/test_output.py:5083-5091 (privilege drop) | TS-24, Input_Bundle_QC/03_Tests_QC.md:68-72 | Every TS-24 bullet holds at those lines; no kit line asks for setgroups. |
| QL1-F17 (OOS) | tests/judge.toml R4-R12 (weight 3, 27 of 36) | JD-15 04:92, JD-12 04:89 | No kit line caps the conduct share of the judge layer. |
| QL1-F18 (OOS) | task.toml:16 (420 min estimate) vs :35 (14400 s agent timeout) | AL-8, Input_Bundle_QC/05_Alignment_QC.md:44 | AL-8 compares the estimate with the work, not with the agent timeout. |
