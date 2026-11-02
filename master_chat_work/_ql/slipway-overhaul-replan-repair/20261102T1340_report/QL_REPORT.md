IST 2026-11-02 13:40 | from QL (relayed by Ayush) | task slipway-overhaul-replan-repair | frozen tree 2f83a9bd6a10

Numbering added by the master: QL1-F1..F18 in the QL's order. Text below is verbatim.

Findings
❌ Fail
[QL1-F1] ❌ IN-12 — The declared category names the engine's subject, not the dominant work.
- Where: task.toml L12 category = "Optimization".
- Evidence: task.toml L7 description = "Repair the shipped stdlib slwopt replan engine, ...". instruction.md L7 "Extract it, work out where it departs from the papers, and repair it there." Keywords include repo-patch. Of the 15 catalogued faults (TRUTH.md L18-51), only 5 touch the objective (DFC-08, 09, 11, 12, 13). Seven are in the incremental cascade or cache (DFC-01..07) and three are in input reading (DFC-10, 14, 15). The subset search is fixed by p11 ("all subsets ... in ascending mask"), so the agent designs no optimiser. This is the gate's own example: a debugging task with a side flavour declared under the flavour. AL-26 catches the same defect.
- Type: Bug/Error.
- Fix: Set category = "Debugging" (or "Software Engineering") and keep optimization as a keyword.
[QL1-F2] ❌ IN-16 — The kind of an edge_lodged amendment that carries no kind is graded, but no paper settles it.
- Where: environment/data/amendment_journal.jsonl L2 and L19; spec_stage_p02_*.md L9-10.
- Evidence:
- L2 is AMD-102 with payload {"required_job":"JOB-1008","requiring_job":"JOB-1000"}, and L19 is AMD-119; neither carries a kind. AMD-116 and AMD-118 (L16, L18) carry "kind":"hard".
- row_provenance_ledger.csv L2 reads AMD-102,kind,amendment_journal.jsonl,in_force,the lodged row settles the kind, and the journal row has no kind.
- Reading A (what is graded): a missing kind means hard, so AMD-102 adds the prerequisite 1000→1008. See tests/test_output.py L3022/L3028 "kind": payload.get("kind", "hard").
- Reading B: p02 L9-10 says "EDG-ADVISORY  the row kind is not hard. An advisory lodgement records an opinion and creates no prerequisite." Under that rule no prerequisite is created.
- Why the shipped engine cannot settle it: data_lineage_and_governance.md lists project.zip among the files that govern nothing.
- Files searched, with no ruling found: p02, p13, directive docx text, glossary, worked_examples, readings_not_in_force, programme contract, lineage, 00_open_this_first, schema reference, precedence_and_order_policy, revision_precedence, publication_form_rules.
- Checkers that depend on it: shipped_invalidation_sets_exact, shipped_work_ledger_exact, shipped_store_summary_exact, shipped_final_optimum_exact, shipped_audit_documents_exact, package_eval_cascade_exact, package_challenge_cascade_exact, package_probe_publication_exact, and 10 of the 12 package_crosswalk_* tests.
- Measured impact: an otherwise-oracle engine that follows Reading B scores 38/112 (0.339) on the test channel in my local harness. On the shipped round, the 16 row for AMD-102 changes from 11,11,0,242,1024,0,11,0 to 1,0,1,252,0,1,0,0.
- Type: Bug/Error.
- Fix: Add a sentence to spec_stage_p13 saying that an edge_lodged amendment whose settled row carries no kind is a hard lodgement, or give AMD-102 and AMD-119 an explicit kind in the generator.
[QL1-F3] ❌ IN-16 — "Amendments applied" (doc 23 line and control_totals.amendments_applied in doc 25) is graded, but no paper defines it.
- Where: output_schema_reference.md L155-160 and L167-174 name the quantity without defining it.
- Reading A (graded): every lodged amendment, rejected ones included, which gives 19. This is shipped publish.py len(records) and the reference chain.
- Reading B: only amendments that took effect, which gives 15. The glossary L49 uses "applied" that way: "| AMD-NOTARGET | p13 | the reversal names no amendment this round applied |". The reference's own AMD-NOTARGET logic agrees, since model.inverse holds only non-rejected amendments. TRUTH.md L240-246 also says "names an amendment no earlier row applied".
- Checkers: shipped_audit_documents_exact, package_probe_publication_exact, package_crosswalk_{every,groups,rules,amendments}_publication_exact.
- Measured impact: an oracle engine that publishes 15 scores 86/112 (0.768). It loses 26 points over one count.
- Type: Bug/Error.
- Fix: Define the quantity in output_schema_reference.md, for example "the amendments applied: every lodged amendment, rejected ones included".
[QL1-F4] ❌ DS-19 — The oracle breaks the instruction's stated reading order, and the judge grades that order (R3).
- Where: instruction.md L3 "Start at /app/data/00_open_this_first.txt, then /app/data/replan_programme_contract.md". tests/judge.toml L40 (R3, weight 3).
- Evidence:
- grep -n "00_open_this_first\|replan_programme_contract" over solution/solve.sh and solution/solve.py returns no hits.
- The oracle's first read under /app/data is project.zip (solve.py extract()).
- TRUTH.md L288-289 still claims "1. Read 00_open_this_first.txt, then the programme contract, then the lineage paper, then the readings paper. Covers R3."
- JD-7 and AL-6 catch the same R3 defect.
- Type: Bug/Error.
- Fix: Make solve.sh open and print /app/data/00_open_this_first.txt, then /app/data/replan_programme_contract.md, before it touches any other file under /app/data.
[QL1-F5] ❌ JD-7 — The oracle does not do what judge criterion R6 requires.
- Where: tests/judge.toml L79; solution/solve.sh L239-248.
- Evidence:
- R6 requires that the agent "printed the work counters of its run stage by stage beside the matching rows of /app/data/withdrawn_counter_publication.csv and named the stages where the two differ".
- check_counters only compares, then prints a count and the first differing stage: report("R6", str(len(differ)) + " stages differ, first " + "/".join(differ[0])).
- Two weaker mismatches: R4's report (L217-218) prints two weighted values but never the kept set; R10's count (L219-220) counts distinct closed sets (found[closed], L186/L198), not subsets.
- Type: Bug/Error.
- Fix: Have check_counters print every matched stage's cells_visited, cells_recomputed and subsets_examined beside the withdrawn row and list every differing stage. Also print the kept set for R4 and count subsets for R10.
[QL1-F6] ❌ TS-25 — A positive test pays for an absence.
- Where: tests/test_output.py L5352-5368 test_delivered_engine_stdlib_only, registered L6048 criteria.delivered_engine_stdlib_only(weight=1).
- Evidence: The pass condition is that no import outside allowed = set(sys.stdlib_module_names) | {PACKAGE_NAME, ""} appears. That is the gate's own example ("a banned import that is absent"). The unrepaired shipped engine earns it: in the ws_shipped harness run it was one of 4 tests paid.
- Type: Bug/Error.
- Fix: Re-register the check as a negative, e.g. negative_engine_imports_outside_stdlib, returning True when a non-stdlib import is found.
[QL1-F7] ❌ AL-28 — One act can trigger two negative judge criteria for more than 5 combined.
- Where: tests/judge.toml L170 (R13, -3), L196 (R15, -3), L183 (R14, -5), L209 (R16, -3).
- Evidence:
- A single invented claim such as "re-ran on three altered rounds and all 25 documents matched", with no such run, fires R13 ("claims that a ... check passed ... where the trajectory shows that check run ... never") and R15 ("states the size or coverage of a check ... as larger than the trajectory shows"). Total: -6.
- Quoting withdrawn_counter_publication.csv's build row (265 visited) as the figure in /app/out/16_work_counters.csv (actual 253) fires R14 and R16. Total: -8.
- Type: Bug/Error.
- Fix: Fold R15 into R13 (or set R15 to -1). Narrow R16 to withdrawn figures reported as the round's standing without attributing them to a delivered file, so R14 and R16 can never fire on the same sentence.
🟡 Minor
[QL1-F8] 🟡 IN-L2 — An unhyphenated compound modifier.
- Where: instruction.md L5 "the rules on duplicate lodgements and double booked group members".
- Type: Suggestion/Improvement.
- Fix: Write "double-booked group members".
[QL1-F9] 🟡 DS-6 — round_header.json carries a control-looking value that no paper defines.
- Where: environment/data/round_header.json L2 "amendment_window": 11.
- Evidence: grep finds the key only in round_header.json, while the round lodges 19 amendments. The generator writes it as len(AMENDMENT_KINDS) (test_output.py L3555). data_lineage_and_governance.md lists what the header governs (round key and index, workbook sheet key, register in force), and this field is not among them.
- Type: Bug/Error.
- Fix: Drop amendment_window from the header and the generator, or define it in a paper.
[QL1-F10] 🟡 DS-6 — The manifest's scope is worded inconsistently across papers.
- Where: output_schema_reference.md L163 "One line per document above, in this order". In the schema file only documents 01..23 stand above 24.
- Evidence: spec_stage_p14_publication.md L6 says "the twenty four documents before it in the order the schema reference lists", and serialisation_and_digest_contract.md L16 says "after the twenty four documents". The oracle's manifest includes 25_summary.json.
- Type: Bug/Error.
- Fix: Change schema L163 to "One line for each of the other twenty four documents, in schema order".
[QL1-F11] 🟡 DS-22 — TRUTH.md misdescribes DFC-16.
- Where: solution/TRUTH.md L55-57 "DFC-16 to DFC-27 are faults ... that the shipped round leaves quiet or coincident: lodgements naming a job of a cycle are rejected under EDG-UNKNOWNJOB".
- Evidence: Reverting DFC-16 alone moves shipped-round documents 02, 19, 23, 24 and 25: edges rejected 178 instead of 181, and the cycle edges EDG-4261/4268/4275 change.
- Type: Bug/Error.
- Fix: State that DFC-16 changes the shipped round's 02/19/23/24/25, and keep "quiet or coincident" for DFC-17..27 only.
[QL1-F12] 🟡 JD-5 — R6 bundles two acts in one criterion.
- Where: tests/judge.toml L79: "printed the work counters ... beside the matching rows ... and named the stages where the two differ".
- Type: Suggestion/Improvement.
- Fix: Keep one observable, e.g. "The agent named the stages where its work counters differ from /app/data/withdrawn_counter_publication.csv."
[QL1-F13] 🟡 AL-18 — The verifier's docstring understates how many rounds the package is driven over.
- Where: tests/test_output.py L9-12 "The package the agent delivered is extracted and driven over three rounds minted from seeds it has never seen".
- Evidence: MINTED_SEEDS (L4951) holds 3 seeds and HELD_ROUNDS (L5242) holds 11, so 14 rounds are driven. Also, the comment at L3796-3801 calls PACKAGE_FILES "the repaired package source", yet it still carries the shipped anchors of DFC-16..27, which solve.py repairs.
- Type: Bug/Error.
- Fix: Say "driven over fourteen rounds (three minted, eleven held)" and describe PACKAGE_FILES as the source with the fifteen catalogued faults repaired.
⚠️ Warn
[QL1-F14] ⚠️ FC-S (structure_qc X1) — Four binary files were skipped by the text scan.
- Evidence: WARN [X1] 4 binary files skipped: cascade_precedence_directive.docx, prior_round_archive.db, project.zip, yard_parameter_workbook.xlsx.
- I re-checked by extracting their text: no em/en dashes and no residue markers.
- Type: Suggestion/Improvement.
[QL1-F15] ⚠️ TS-23 — There are 49 checks against a cap of 35.
- Evidence: tests_qc WARN [A3] 49 checks; cap is 35; registrations at test_output.py L6045-6093.
- Type: Suggestion/Improvement.
[QL1-F16] ⚠️ TS-24 — The privilege drop keeps the root supplementary group.
- Where: test_output.py L5083-5091 os.setgid(RUN_UID) then os.setuid(RUN_UID), with no os.setgroups([]).
- Evidence: In the pinned verifier base image, root groups [0] became after uid 65534 gid 65534 groups [0].
- This is not exploitable as shipped: /tests is go-rwx, /logs/verifier is root 755, and the reference dirs are 0700.
- Type: Suggestion/Improvement.
[QL1-F17] ⚠️ JD-15 — Nine weight-3 checks of specific verification acts carry most of the judge channel.
- Where: tests/judge.toml R4-R12.
- Evidence: R4-R12 together are 27 of the 36 positive judge points, or 0.375 of total reward. A correct engine verified some other way caps at 0.5 + 9/36×0.5 = 0.625. Each criterion on its own is legitimate (it serves a stated requirement at weight 3).
- Type: Suggestion/Improvement.
[QL1-F18] ⚠️ AL-8 — The expert time estimate exceeds the agent's budget.
- Where: task.toml L16 expert_time_estimate_min = 420.0 (7 h) against L35 agent timeout_sec = 14400.0 (4 h).
- 27 repairs over 58 files make the size plausible, but an expert estimate above the budget is borderline.
- Type: Suggestion/Improvement.
