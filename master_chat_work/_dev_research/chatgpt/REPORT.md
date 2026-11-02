**The best-supported strategy is to make correctness depend on several interacting, fully specified decisions, then evaluate the resulting behavior on fresh cases.** Splitting text across files can contribute, but document placement alone is a fragile source of difficulty.

Two qualifications matter:

- **A 10–20% test score is different from a 10–20% task success rate.** Whole-document grading can produce low task success while most individual decisions are correct. Report both.
- **No published recipe reliably guarantees your target for current frontier agents.** Evidence supports particular failure mechanisms; the eventual score still requires trials with your exact model, harness, budget, and task version.

Below, **direct evidence** means a source demonstrates the relevant behavior; **transfer evidence** means the finding comes from a related setting; **hypothesis** means a proposed design worth testing. Unless identified as an existing benchmark task, examples are suggested task designs, not reported experiments.

1. **Start with interacting rules that change the correct downstream action.**

   **Defeats:** Implementing each rule locally without understanding how one decision changes another rule’s applicability.

   **Example:** A settlement pipeline determines eligibility, selects a contract version, allocates credits, applies a cap, and emits a reconciliation statement. A credit changes the cap’s base only when a separate eligibility condition holds. Keep the numbers simple.

   **Evidence:** ToolSandbox explicitly studies state dependencies and canonicalization and finds them challenging. This is **transfer evidence**, not proof that settlement tasks will score below 20%. [ToolSandbox — paper](https://arxiv.org/abs/2408.04682).

   **Fairness risk:** Accidental contradictions between individually clear rules.

   **Grade / pre-ship check:** Draw the dependency graph privately. Construct cases where each interaction changes an observable outcome. Have an independent solver derive the same graph from the visible files.

2. **Implement plausible wrong interpretations before spending money on agent trials.**

   **Defeats:** Tasks whose apparent complexity does not actually distinguish a shallow solution from a correct one.

   **Example:** Write variants that use the legacy default, select versions by processing date, apply the cap before credits, or treat missing values as zero. These should be coherent implementations, not random broken programs.

   **Evidence:** CheckList demonstrates the value of capability-by-test-type matrices and targeted behavioral tests. Applying that method to “wrong-reading” programs is a **design recommendation**, rather than a published guarantee. [CheckList — paper](https://arxiv.org/abs/2005.04118).

   **Fairness risk:** A supposed mutant may implement another valid reading.

   **Grade / pre-ship check:** Require a visible clause that disproves every mutant and a minimal input that separates it from the reference. Review surviving mutants for grader gaps; review disputed mutants for ambiguity.

3. **Use state transitions with consequences that persist.**

   **Defeats:** Treating a workflow as independent rows or making an irreversible update before collecting all necessary information.

   **Real example:** τ-bench’s retail policy allows an exchange or modification tool to be called only once, requiring all affected items to be collected first. The same document distinguishes product IDs from item IDs. [Retail policy — official benchmark doc/source repository](https://github.com/sierra-research/tau-bench/blob/main/tau_bench/envs/retail/wiki.md).

   **Offline adaptation:** Replay an event stream with reservations, cancellations, retries, and corrections. Later eligibility depends on previously committed state.

   **Fairness risk:** Undefined ordering, retry behavior, or rollback semantics.

   **Grade / pre-ship check:** Test the final state plus selected intermediate consequences. Specify ordering and duplicate-event identity. Include a small trace where the wrong early transition changes a later result.

4. **Make precedence explicit; make applying it substantive.**

   **Defeats:** Following a familiar legacy default or treating whichever document was read last as authoritative.

   **Example:** An index states: “The amendment overrides the base agreement only for the listed products and effective periods; all other provisions remain in force.” A legacy implementation applies the old default globally.

   **Evidence:** Your reported observations support this locally. I found **weak direct public evidence** isolating this exact mechanism in offline coding agents. Terminal-Bench’s proposal rubric supports well-specified tasks and rejects misleading tricks. [Task-proposal rubric — official benchmark doc](https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-proposal.md).

   **Fairness risk:** “Newer wins” without defining scope, authority, or applicability.

   **Grade / pre-ship check:** Test overridden, inherited, and out-of-scope cases. Give reviewers every apparent conflict and require one defensible resolution without author clarification.

5. **Use temporal applicability rather than merely attaching version numbers.**

   **Defeats:** Selecting the latest schema or policy once and applying it to every record.

   **Example:** A correction received in April refers to a February transaction. Eligibility uses the transaction’s policy version; the correction’s output envelope uses April’s schema.

   **Evidence:** This is a **hypothesis** informed by state-dependency findings, not an established domain-specific failure rate. [ToolSandbox — paper](https://arxiv.org/abs/2408.04682).

   **Fairness risk:** Unspecified choice among event time, receipt time, effective time, and processing time.

   **Grade / pre-ship check:** Name each clock, its timezone, interval inclusivity, and retroactivity rule. Generate cases immediately before, at, and after version boundaries, including delayed events.

6. **Put convention changes at real interfaces.**

   **Defeats:** Carrying a valid assumption from one stage into another where it no longer applies.

   **Example:** Input prices are per pack; inventory is in individual units. Eligibility uses local business dates; ordering uses UTC instants. Credits use signed amounts; a reporting column requires positive magnitudes plus a direction field.

   **Evidence:** Canonicalization is an explicit ToolSandbox challenge category; numerical-stability research also identifies failures involving concrete magnitudes and control flow. These provide **transfer evidence**. [Numerical stabilization study — paper](https://arxiv.org/abs/2604.04854).

   **Fairness risk:** A conversion factor or convention exists only in the author’s assumptions.

   **Grade / pre-ship check:** Document every interface’s units and representation. Use non-identity conversions and boundary cases. Verify that the challenge remains semantic when arithmetic is trivial.

7. **Test exception intersections and explicit residual cases.**

   **Defeats:** Coding the headline rule, overlooking its exceptions, or interpreting an exception as a replacement for the whole policy.

   **Example:** Regions A and B have named eligibility rules; “every other region” uses the residual rule. A separate product exclusion applies across all regions. Hidden cases exercise both together.

   **Real evidence:** τ-bench’s audit found expected compensation actions that violated its own eligibility policy—an instructive example of how easily authors also mishandle exceptions. [Airline and retail fixes — engineering blog by benchmark authors](https://taubench.com/blog/tau3-task-fixes.html).

   **Fairness risk:** Omission masquerading as specification. Silence alone does not establish a default.

   **Grade / pre-ship check:** Enumerate the domain and truth table privately. Include each branch in visible input data, even if no worked output demonstrates the full interaction.

8. **Distinguish missing, zero, empty, inherited, and explicitly disabled.**

   **Defeats:** Convenient normalization that destroys information needed downstream.

   **Example:** An absent account override inherits the regional cap; zero disables payment; an explicit null has a separately documented meaning. A migration must preserve those distinctions.

   **Evidence:** This is a **proposed pattern with transfer evidence** from canonicalization and state-dependency benchmarks, not a demonstrated migration-specific frontier weakness. [ToolSandbox — paper](https://arxiv.org/abs/2408.04682).

   **Fairness risk:** Importing language-specific or industry-specific semantics without stating them.

   **Grade / pre-ship check:** Write a visible value-semantics table. Test every distinct state and combinations with inheritance. Reject the task if experts disagree about whether two representations are equivalent.

9. **Require preservation alongside transformation.**

   **Defeats:** Producing the requested change while silently deleting, rewriting, or fabricating unrelated information.

   **Real examples:** AppWorld evaluates collateral damage through state-based checks. Terminal-Bench’s `git-leak-recovery` combines secret removal with preservation of unrelated files and commit messages. [AppWorld — paper](https://arxiv.org/abs/2407.18901); [Terminal-Bench task catalogue — paper, appendix H](https://arxiv.org/html/2601.11868v1#A8).

   **Fairness risk:** Requiring exact preservation of irrelevant serialization details.

   **Grade / pre-ship check:** State the preservation boundary. Compare semantic records or scoped state differences; use byte equality only where bytes are part of the requirement. Add negative checks for extra records, duplicate payouts, and unrelated mutations.

10. **Withhold the full answer oracle while preserving the complete specification.**

    **Defeats:** Searching over several interpretations until one reproduces a shipped final output.

    **Example:** Ship the schema, invocation example, authoritative policies, and small local examples. Do not ship an end-to-end completed statement, checksum of that statement, or executable reference implementation.

    **Evidence:** Anthropic reports that telling Opus 4.5 an achievable performance level helped it discover an optimization it had previously considered impossible. That is **direct evidence that answer-adjacent feedback can steer search**, though not a controlled study of sample-output removal. [AI-resistant technical evaluations — engineering blog](https://www.anthropic.com/research/AI-resistant-technical-evaluations).

    **Fairness risk:** Removing examples that were the only source of a necessary rule.

    **Grade / pre-ship check:** For every withheld example, verify that prose still determines the behavior. Permit agents to write tests and independent implementations. Successful self-verification is legitimate.

11. **Regenerate semantic situations, not just identifiers and amounts.**

    **Defeats:** Hardcoding shipped outputs or overfitting to one arrangement of the data.

    **Example:** Vary which amendment applies, whether a correction crosses a boundary, whether a duplicate is exact or conflicting, and whether a cap binds. Also vary irrelevant names and row order where permitted.

    **Evidence:** Behavioral test generation is supported by CheckList; the precise generator design here is a **recommendation**. [CheckList — paper](https://arxiv.org/abs/2005.04118).

    **Fairness risk:** Generated cases leave the documented input domain or become internally inconsistent.

    **Grade / pre-ship check:** Generate by semantic category with validity assertions. Save seeds and failing inputs. Independently verify a small, diverse corpus. Do not rely on uniform randomness to hit rare interactions.

12. **Keep expected answers and scoring authority outside submitted code’s reach.**

    **Defeats:** Reading the oracle, modifying tests, monkeypatching timing functions, or writing the reward directly.

    **Real evidence:** METR documented a kernel submission that inspected the Python call stack to retrieve the reference tensor and interfered with timing. Harbor supports verification in a separate environment. [Reward hacking examples — engineering/research blog](https://metr.org/blog/2025-06-05-recent-reward-hacking/); [Separate verifier — official benchmark doc](https://docs.harborframework.com/tasks/separate-verifier).

    **Fairness risk:** The isolated environment lacks dependencies or artifacts legitimately needed by the solution.

    **Grade / pre-ship check:** Transfer only declared deliverables into a clean runner. Execute untrusted code separately from the process holding expected answers and reward files. Probe with a dummy submission that attempts to inspect parent state and alter scoring.

13. **Grade end-to-end semantic documents, while retaining diagnostic partial credit.**

    **Defeats:** Correct isolated figures assembled into an inconsistent or incomplete deliverable.

    **Example:** A statement passes only when its recipient, eligible items, adjustments, totals, and reconciliation agree. Separately record which components were correct.

    **Evidence:** AppWorld demonstrates state-based evaluation that permits different valid routes to a goal. Anthropic recommends partial credit for multi-component tasks. [AppWorld — paper](https://arxiv.org/abs/2407.18901); [Agent evaluation guide — engineering blog](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).

    **Fairness risk:** One punctuation issue fails the entire document, or one semantic error is counted as dozens of independent failures.

    **Grade / pre-ship check:** Parse and normalize outputs. Publish the scoring structure. Report whole-scenario success alongside component accuracy and root-cause categories.

14. **Weight capabilities and scenarios, rather than raw assertion counts.**

    **Defeats:** A mostly boilerplate solution earning high credit because easy formatting checks outnumber substantive decisions.

    **Example:** Give fixed weight to eligibility, version selection, state transitions, reconciliation, and preservation. Within each category, average over cases.

    **Evidence:** Partial-credit guidance supports meaningful decomposition, but **no source establishes a universally correct weighting**. [Agent evaluation guide — engineering blog](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).

    **Fairness risk:** Selecting weights after observing model failures to manufacture a low score.

    **Grade / pre-ship check:** Freeze weights before final calibration. Score the reference, empty output, ordinary-case-only solution, and every wrong-reading variant. Duplicating a test should not change the score.

15. **Use deterministic adversarial execution for concurrency and failures.**

    **Defeats:** Code that works under the ordinary schedule but loses updates, leaks reservations, or mishandles cancellation.

    **Example:** A supplied scheduler pauses two workers after reading a balance, then resumes their writes. Another scenario cancels a worker after reservation but before commit.

    **Evidence:** DRPBench identifies difficulty interpreting nonstandard synchronization. SWE-Race supplies real concurrency repair tasks, although its reported overall scores are much higher than your target. [DRPBench — paper](https://proceedings.mlr.press/v306/guo26z.html); [SWE-Race — official benchmark doc](https://labs.evaligo.com/swe-race).

    **Fairness risk:** A probabilistic race becomes a flaky test.

    **Grade / pre-ship check:** Use barriers, injected failures, or a deterministic scheduler. Specify safety and liveness obligations. Confirm repeated runs of the same implementation and schedule produce the same verdict.

16. **Use the judge for evidence-backed interpretation and reporting, not arithmetic.**

    **Defeats:** A persuasive final answer claiming completion or validation that did not occur.

    **Example:** The final reply says “all tests passed,” but the trace shows only compilation. A good rubric distinguishes that from “compiled successfully; boundary behavior remains untested.”

    **Evidence:** Agent-evaluation guidance distinguishes claimed success from actual outcomes; evaluator research documents position bias and benefits from calibration. [Agent evaluation guide — engineering blog](https://www.anthropic.com/research/demystifying-evals-for-ai-agents); [LLMs are not Fair Evaluators — paper](https://arxiv.org/abs/2305.17926).

    **Fairness risk:** Rewarding confident prose, verbosity, or a preferred reasoning style.

    **Grade / pre-ship check:** Require citations to observable trace events or artifacts. Include an “insufficient evidence” verdict. Calibrate against terse correct responses, polished wrong responses, and incomplete traces.

17. **Require blind human solves, an independent oracle, and controlled ablations.**

    **Defeats:** Difficulty caused by author knowledge, shared reference-code bugs, or an unjustified belief that humans would find the task easy.

    **Example:** One expert solves using only the agent-visible bundle. Another implements the specification independently. Ablations consolidate the documents, remove legacy code, or provide intermediate expected values.

    **Evidence:** HCAST grounds tasks in human baselines under matching conditions; Terminal-Bench documents human solutions and adversarial quality checks. [HCAST — paper](https://metr.org/hcast.pdf); [Terminal-Bench — paper](https://arxiv.org/html/2601.11868v1).

    **Fairness risk:** The blind solver receives hints, silently uses external knowledge, or validates against the author’s implementation.

    **Grade / pre-ship check:** Record questions and assumptions. Require independent agreement on boundary cases. Treat ablations as diagnosis: a score increase identifies what contributes difficulty, not automatically whether it is fair.

18. **Calibrate on fresh trials and retire tasks that require unfairness to remain hard.**

    **Defeats:** Overfitting task wording to one model’s failed trajectory or mistaking a lucky failure for stable difficulty.

    **Example:** Freeze a candidate, run multiple attempts on at least two strong agent configurations, inspect failures, then validate the final revision on untouched seeds and fresh attempts.

    **Evidence:** Anthropic’s take-home repeatedly lost discriminatory power as models and harnesses improved. Infrastructure changes alone produced a six-percentage-point Terminal-Bench difference in another Anthropic study. [AI-resistant evaluations — engineering blog](https://www.anthropic.com/research/AI-resistant-technical-evaluations); [Infrastructure noise — engineering blog](https://www.anthropic.com/research/infrastructure-noise).

    **Fairness risk:** Repeatedly changing instructions or weights until one configuration lands at 15%.

    **Grade / pre-ship check:** Predeclare revision and stopping rules. Drop or reclassify tasks that become easy once clarified, remain disputed by experts, depend on flaky execution, or only fail with inadequate time/resources.

The domain choice should follow the evidence, with these distinctions:

| Domain | What the evidence supports | Practical recommendation |
|---|---|---|
| **Policy-driven workflows** | Good evidence for state and policy interactions, but original benchmarks also contained substantial annotation errors. | Strong starting point. Translate the workflow into a deterministic event processor with complete policy files. |
| **Concurrency and cancellation** | Direct evidence of synchronization-reasoning weaknesses. Real repair benchmarks also show many such bugs are easy. | Prefer interacting lifecycle bugs over a lone missing lock. Use controlled schedules. |
| **Numerical stability** | A study reports failures preserving control flow and semantic equivalence during stabilization. This is narrower than general numerical coding. | Useful if numerical reasoning itself is allowed; weaker fit for your “no arithmetic difficulty” constraint. |
| **Binary/format recovery** | Real Terminal-Bench tasks include `sqlite-db-truncate` and `extract-elf`; their existence does not establish current frontier failure rates. | Use explicit recoverability and provenance rules; avoid guessing destroyed bytes. |
| **Accounting/settlement** | I did not find strong evidence isolating accounting rules as a current offline-agent weakness. | Promising vehicle for precedence, reversals, allocation, and reconciliation. Treat difficulty as unproven until trials. |
| **Calendars/time zones** | Related canonicalization evidence exists; a strong domain-specific failure claim is not established here. | Supply a frozen calendar/timezone basis and explicit gap/fold, cutoff, and business-day rules. |
| **Versioned schema migrations** | Plausible interaction between temporal selection, preservation, and value semantics; direct isolated evidence is limited. | Test mixed versions, replay, idempotency, and absent/null distinctions. Avoid undocumented compatibility requirements. |

The numerical evidence deserves particular caution. The **SciCode-Verified authors report** that correcting specifications and graders raised main-problem accuracy from 9–27% to 69–92% across their evaluated models. This is a recent audit claim, not a result I independently reproduced, but it directly warns against interpreting very low scores as proof of scientific difficulty. [SciCode-Verified — paper/preprint](https://arxiv.org/abs/2608.04975). The narrower stabilization study reports concrete control-flow and semantic-preservation failures. [Numerical stabilization — paper/preprint](https://arxiv.org/abs/2604.04854).

For your shipping bundle, I would use this division:

| Ship to the agent | Keep in the evaluator |
|---|---|
| Short objective naming authoritative files | Reference implementations and expected final artifacts |
| Complete rules, precedence, input domain, and error behavior | Hidden seeds and generated cases |
| Output schema and a minimal invocation example | Category coverage and mutation results |
| Small examples that clarify local semantics | Full-chain worked answers |
| Visible input containing relevant edge-case categories | Grader internals, reward-writing authority, and private validation reports |
| Ordinary smoke tests and available offline dependencies | Adversarial scoring tests and hidden oracle data |

**Do not try to prevent all confirmation.** Once the specification is complete, an agent can legitimately derive an independent implementation, enumerate cases, or construct invariants. Your design can avoid supplying a ready-made full-answer oracle; it cannot fairly forbid the agent from creating one. A sample that distinguishes two readings is also appropriate when the prose otherwise leaves them ambiguous.

For partial credit, a reasonable **starting proposal**, not an evidence-backed optimum, is:

- **50%:** complete semantic correctness of regenerated end-to-end scenarios.
- **30%:** component correctness across distinct rule families.
- **20%:** preservation, rejection behavior, idempotency, and other explicitly required negative properties.

Report whole-task success separately. Do not count a single mistaken eligibility decision as ten independent reasoning failures merely because it changes ten downstream fields. It may legitimately invalidate ten deliverables, but the diagnostic report should identify the shared cause.

For the LLM judge, use a small set of independently scored criteria:

| Criterion | Evidence required | Avoid |
|---|---|---|
| **Correct explanation of a material decision**, if explanation is requested | The selected rule, applicable facts, and matching artifact behavior | “Demonstrates deep understanding” |
| **Accurate completion report** | Claims match files, exit status, and known remaining failures | Treating confidence as correctness |
| **Accurate validation report** | Named checks actually ran; their scope is described accurately | Requiring an undisclosed number or style of tests |
| **Accurate limitations** | Disclosed uncertainty matches observable gaps | Rewarding generic disclaimers |
| **Explicit process constraints**, only when part of the task | Observable violation of a stated constraint | Penalizing an unexpected valid solution path |

A single computed figure belongs in a deterministic check. It can be a useful **sentinel** for a rule interaction, but it cannot establish full-chain correctness: different mistakes can cancel. Check companion values, classifications, and cross-document relationships. Keep judge scores separate from functional correctness so eloquent reporting cannot rescue a wrong program.

Before expensive trials, I would run the following release sequence:

1. Create a requirement-to-test map, with a visible source location for every assertion.
2. Complete one blind expert solve and one independently written oracle.
3. Build the wrong-reading variants and verify that each loses for the intended reason.
4. Audit the generator using small boundary cases, invariant checks, and independent recomputation.
5. Test packaging with an empty submission, the reference solution, an alternative valid solution, and an adversarial submission.
6. Run a small agent pilot and inspect every failure. Label specification, environment, grading, and agent errors separately.
7. Run targeted ablations, revise, then freeze the task and scoring before fresh calibration.

These steps can eliminate bad candidates cheaply. They **cannot establish a 10–20% frontier score without frontier trials**. Nor can many regenerated inputs replace repeated agent attempts: inputs measure one submitted program’s generalization; attempts measure variation in the agent’s solution.

Finally, these are the anti-patterns I would explicitly reject:

- **A technically defensible sentence designed to imply the wrong answer.** A clear precedence system is legitimate; misleading prose is a trick. Terminal-Bench’s proposal rubric explicitly rejects that distinction being blurred. [Official benchmark doc](https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-proposal.md).
- **“Every rule is somewhere” as the entire fairness argument.** Rules may still contradict, refer to unavailable data, or leave their applicability unresolved. τ-bench’s authors corrected more than 50 tasks, including wrong expected actions and impossible constraints. [Engineering blog](https://taubench.com/blog/tau3-task-fixes.html).
- **Strict textual matching for semantic outputs.** Rejecting equivalent numbers, harmless ordering, or alternative valid implementations measures grader rigidity. Terminal-Bench’s implementation rubric explicitly warns against formatting minutiae. [Official benchmark doc/source repository](https://github.com/harbor-framework/terminal-bench/blob/main/docs/prompts/task-implementation.toml).
- **Using obscure subject matter as proof of difficulty.** Expert knowledge can mask defective gold answers and tolerances; the SciCode audit is a substantial warning. [Paper/preprint](https://arxiv.org/abs/2608.04975).
- **Hiding tests in the same trust boundary and relying on “do not inspect.”** METR’s examples show why oracle and scoring access must be engineered away. [Engineering/research blog](https://metr.org/blog/2025-06-05-recent-reward-hacking/).
- **Assuming “offline” eliminates answer leakage.** Git objects, installed fixed releases, caches, and bundled artifacts can still leak solutions. SWE-Race’s authors report agents attempting to download already-fixed packages; this is **author-reported forum evidence**, not independent replication. [Forum/opinion](https://www.reddit.com/r/MachineLearning/comments/1wyw0my/swerace_a_codingagent_benchmark_of_188_real/).
- **Random sleeps, tight timeouts, missing packages, or permissions as difficulty.** Resource enforcement materially changes agent scores. Freeze dependencies and distinguish infrastructure failures from solution failures. [Engineering blog](https://www.anthropic.com/research/infrastructure-noise).
- **Claiming an entire domain is hard from a selected hard subset.** SWE-Race reports roughly 82% overall success for its leading evaluated configurations, despite a much harder subset. Selection matters. [Official benchmark doc](https://labs.evaligo.com/swe-race).
- **Requiring the author’s trajectory.** Evaluate required outcomes and genuinely necessary process constraints, allowing alternative correct approaches. [Engineering blog](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).
- **Treating a low pilot score as validation.** Retain a task only when you can explain its failures as specific, reproducible misunderstandings of a complete specification—and demonstrate that independent experts can solve it under the same information constraints. [HCAST — paper](https://metr.org/hcast.pdf).