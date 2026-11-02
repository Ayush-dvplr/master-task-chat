# Intake: external report to candidate lever

External research is a source of hypotheses. A cited paper can support a failure mechanism; only a local fresh blind result on a valid task design can support a pipeline lever. This distinction follows the present blind-evidence rule in `master_chat_tasks/knowledge/LEVER_RULES_v3.md:227-243`.

## 1. Preserve and extract

Save the returned report unchanged in the master's research area and record provider, model/mode, prompt number and version, retrieval date, and source URLs. Do not copy proposed task prose or code into a live bundle. For each distinct proposal, create one candidate row:

| Field | Required content |
|---|---|
| `candidate_id`, `status` | Stable ID; `RESEARCHED`, `REJECTED`, `DESIGN_BLIND`, `PILOT`, or `ACCEPTED`. |
| `claim_type`, `source` | `OBSERVED`, `INFERRED`, or `UNVERIFIED`; direct source URL/DOI and exact section, figure, or page. |
| `mechanism`, `wrong_program` | The precise plausible wrong algorithm/reading and why it can produce a valid document. |
| `visible_contract` | Sentence(s) that determine every graded rule, branch, tie-break, output shape, invocation, and limit. |
| `shipped_case`, `hidden_counterexample` | Minimal instances and expected outputs from a second, independent calculation. |
| `generator`, `oracle`, `ownership` | Seed/bounds plan, independent expected-value method, test observable and owner, no double payment. |
| `predicted_weight`, `runtime` | Positive test share; reference and plausible solver time/memory; proposed stated limit and margin. |
| `fairness_risk`, `qc_risk` | Ambiguity, missing sentence, out-of-domain seed, oracle bug, timeout leakage, test overlap. |
| `blind_result`, `decision` | Fresh blind program, three hidden-seed outcomes, strongest generic solver outcome, WRONG/TIMEOUT/CRASH split, reviewer and date. |

Primary citations are checked by opening the cited paper/report and verifying the claimed figure and setup. A source about a different model, benchmark, or year keeps that qualifier. An inaccessible source stays `UNVERIFIED`; a new task idea remains `INFERRED` even when its background paper is real. The local 90-task contrast is associative and contains inferred hidden-share labels, so it does not by itself prove a new lever (`master_chat_tasks/knowledge/ANGLES.md:3,8-12`).

## 2. Fast rejection before a build

Reject a candidate when the decisive property is hidden by silence, two readings fit the shipped evidence, the hidden generator needs an unstated branch/key, the oracle is not independent, or the loss is solely a grader defect. These fail current rule and validity requirements (`master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md:25-30`; `master_chat_tasks/knowledge/LEVER_RULES_v3.md:162-180`). Reject if its strongest generic solver is exact under the proposed limit, or if the agent's likely wrong output cannot be separated by a valid hidden input (`master_chat_tasks/knowledge/LEVER_RULES_v3.md:240`). Mark a conjecture with no runnable separating case `HOLD`, not proven.

## 3. Blind before any full build

Prepare only a small design packet: draft instruction, rule register, one shipped sample, a three-seed hidden-instance specification, and an independent expected-value calculation. This is a design artifact, not a task bundle. Give the packet to a fresh blind coding agent without the research report, wrong-program description, oracle, or hidden seeds. The existing design-stage rule calls for one fresh read before full build, then redesign if it matches the oracle on the shipped sample and three hidden seeds (`master_chat_tasks/knowledge/LEVER_RULES_v3.md:228`).

Have a separate reviewer run the blind program on the three hidden seeds and compare exact outputs with the independent calculation. Try the strongest generic solver for the core. Record for each seed: valid/wrong output, timeout, crash, and first differing field. A candidate passes this cheap gate only if the blind program loses on valid in-domain input and the generic solver does not erase the difficulty. Timeout/crash is provisionally acceptable only under the current three-condition hidden-scale rule (`master_chat_tasks/knowledge/LEVER_RULES_v3.md:87-90`). If it passes, mark `PILOT`; do not mark `PROVEN`.

## 4. Promote only with quality evidence

For a `PILOT`, estimate the lever's independent positive test share and verifier cost. Target the current design conditions: lever share at least 40%, no design blind above tests 65, verifier worst case at most 90% of its stated limit, reference at most one quarter of that limit, and a plausible final at most 35 before the real gate (`master_chat_tasks/knowledge/LEVER_RULES_v3.md:90`). A full build then follows the existing sequence: build, three fresh blind reads, full QC/fixes, freeze, one valid paid run (`master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md:65-68`). Three blind reads, not a borrowed solver or a self-marked judge score, are the round evidence (`master_chat_tasks/knowledge/LEVER_RULES_v3.md:229-243`).

Record rejected and failed pilots with their separating cases and reason. Reuse the mechanism only after changing the design and repeating a fresh blind; do not re-run unchanged frozen bytes to search for a favorable score (`master_chat_tasks/knowledge/LEVER_RULES_v3.md:241-244`).
