# fa7c65bd-ff01-50e7-b3ba-34fbd5df860d: Data Processing

## Assignment and score

Implement a spectrum-clearing engine with revisioned grants, half-open time-frequency rectangles, preemption and signed correction allocation. Evidence: `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/instruction.md:1`.

Opus tests **23.08**, rubric **21.43**, final **22.25**; 15 test checks and 17 judge criteria. Reward and summary agree, verifier finished, exception_info is null, and all 10 captured `/app/out` artifacts have status `ok`. Evidence: `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/pass_summary.json:$.per_run[0]`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/run_1/verifier/ctrf.json:$.results`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/run_1/verifier/score.json:$.rubric`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/run_1/result.json:$.verifier,$.exception_info`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/run_1/artifacts/manifest.json`.

## Where points went

Eight fresh scenarios fail: revision cells/scalars, activation ID, half-open boundary, guard abutment, correction tie, half-up midpoint and exclusion span. Judge validation probes also fail. Evidence: `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/instruction.md:1-7`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/environment/data/schema.md:3-55`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/tests/test_output.py:342-384`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/solution/TRUTH.md:5-25`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/run_1/verifier/ctrf.json:$.results.tests`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/trajectories/claude-opus-5/run_1/verifier/score.json:$.rubric`.

Failed positive test names: `scenario_revision_cells` (5), `scenario_revision_scalar` (5), `scenario_activation_identifier` (5), `scenario_half_open_boundary` (5), `scenario_guard_abutment` (5), `scenario_correction_tie` (5), `scenario_half_up_midpoint` (5), `scenario_exclusion_span` (5)

Failed positive judge criteria: J2(5, trajectory): The agent validates revision, cancellation, and equal-rank conflict handling with explicit assertion…, J3(5, trajectory): The agent validates a time-by-frequency-by-cell partition with explicit expected cut points, half-op…, J4(5, trajectory): The agent validates guard-band shrinkage, exclusion precedence, primary activation priority, and det…, J5(5, trajectory): The agent validates auction revision selection, half-open rate lookup, and one complete gross-cents…, J6(5, trajectory): The agent validates winner and owner revenue shares with an independently calculated case that expos…, J7(5, trajectory): The agent validates positive and negative correction allocation with explicit floor shares, fraction…, J8(5, trajectory): The agent executes a purpose-built nonvisible extract and asserts independently calculated expected…, J9(3, trajectory): The agent checks the exact ten artifact paths and validates required top-level fields and row orderi…, J10(3, trajectory): The agent independently recomputes at least one input digest and every audit-chain transition from c…, J11(3, trajectory): The agent reruns the delivered script after JSONL row reordering and verifies canonical report stabi…. Fired negative criteria: none. Complete names, weights and justifications: `run_evidence.json:$[99].failed_criteria`; `run_evidence.json:$[99].fired_negatives`.

**WRONG vs timeout/crash.** 8 positive checks failed and 4 passed. The agent produced captured outputs and no top-level infra exception is recorded (`result.json:$.exception_info`; manifest). Test CTRF has no assertion messages; test wrappers often convert exceptions to `False`. Thus the exact WRONG/TIMEOUT/CRASH split is **UNVERIFIED**. The main wrong-answer mechanism above is **INFERRED** from the check names, output, author truth and judge reasons. A declared time limit in a final message is not a recorded infrastructure timeout.

## Fairness and QC fit

Contract and scenarios align, but each scenario compares all nine reports at once and catches every exception. It needs field or report-level credit and explicit failure causes for our QC. Evidence: `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/instruction.md:1-7`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/environment/data/schema.md:3-55`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/tests/test_output.py:342-384`; `anubis-stage-2/fa7c65bd-ff01-50e7-b3ba-34fbd5df860d/solution/TRUTH.md:5-25`.

| Check | Fit | Reason |
|---|---|---|
| IN-17 | PASS | The instruction gives the deliverable and contract pointer; compare any input-specific hint against shipped data. |
| AL-1 | LIKELY PASS | The contract/data grounding and any withheld rule are described above. |
| AL-27 | LIKELY PASS | Named checks construct relevant fresh/hidden cases; full adjacent-pair trace was not rerun. |
| IN-8 | LIKELY PASS | Same reachability question as AL-1, including judged outcomes. |
| CL-4 | LIKELY FAIL | Compare whole-object/group equality with a one-fact perturbation; explicit exact-output wording counts as an exception. |

QC authority: `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/01_Instruction_QC.md:38,47`; `05_Alignment_Integrity_QC.md:21,38`; `Final_checklist.md:491`. No task-local QC report was found (`run_evidence.json:$[99].qc_files=[]`). These are read-only fit judgments, not a full QC run.
