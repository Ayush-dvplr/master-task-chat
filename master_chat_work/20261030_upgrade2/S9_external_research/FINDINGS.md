VERDICT: Six paste-ready research prompts and a blind-first intake process are complete; the requested S9_external destination was outside this session's writable root.

## Q1. What is already known, and what should external research avoid repeating?

**Finding.** Held-out test weight and observable verification probes are the strongest current directions; small stated-rule traps, generic reruns, and explicit algorithm hints have repeatedly been weak. The external prompts require every graded rule to be stated in shipped documents, valid in-domain hidden inputs, and a strong agent's plausible wrong result. `KNOWN.md` summarizes the evidence and limits in one page. Evidence: `master_chat_tasks/knowledge/ANGLES.md:8-16`; `master_chat_tasks/knowledge/LEVER_RULES_v3.md:77-113`; `master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md:25-30,49-58`; `REQUEST.md:17-20` (U9-U12).

**Recommendation 1.** Give `KNOWN.md` to the master as a filter when it reviews external reports, while pasting the self-contained prompts without internal paths. Expected gain: fewer repeated weak ideas and clearer fairness screening. Risk: current local findings are not universal across models, and some teammate labels await a second review (`master_chat_tasks/knowledge/TEAMMATE_MODELS_v1.md:3`). Verify by checking every proposed lever against `KNOWN.md` and retaining any directly sourced counterevidence.

## Q2. Which external research questions are worth asking?

**Finding.** `PROMPTS.md` has six independent prompts: (1) ChatGPT Deep Research on 2025-2026 coding-agent failure evidence; (2) Gemini Deep Research on hidden-instance task designs; (3) judge rubric design; (4) token/time efficiency; (5) parallel Docker scheduling on one Mac; (6) adversarial search for new fair levers. Each includes a goal, standalone context, exact questions, a required lever table with mechanism, agent failure, deterministic grading, build cost and sources, and explicit citation/uncertainty rules. Evidence: `PROMPTS.md` sections 1-6; source constraints at `master_chat_tasks/prompts/templates/P1_chatgpt_ideas_v3.md:9,28-36`.

**Recommendation 2.** Ayush can paste prompts 1 and 2 into their named research modes, then use 3-6 according to the bottleneck. Expected gain: cited candidate designs and method answers without a local network or paid agent run. Risk: external reports may invent citations or infer a lever from unrelated benchmarks. Verify source ledger entries against primary papers and mark unsupported rows `UNVERIFIED` before intake. No external research was run in this session.

## Q3. How should reports become candidate levers before a build?

**Finding.** `INTAKE.md` defines source verification, candidate fields, fast fairness rejection, a design-only blind with three hidden seeds and a strong generic solver, and promotion through the existing three-blind/QC/freeze/one-run gate. This follows the current design-blind and valid-run rules. Evidence: `master_chat_tasks/knowledge/LEVER_RULES_v3.md:227-244`; `master_chat_tasks/prompts/templates/_COMMON_RULES_v5.md:49,65-68`.

**Recommendation 3.** For each returned report, create a candidate row and run the small blind before commissioning a full bundle. Expected gain: reject leaky or invalid ideas earlier, saving build and paid-probe time. Risk: a small blind can miss failures that appear only in a full task. Verify promotion with three fresh blind reads, QC, and one valid run on frozen bytes as the current pipeline requires.

## Delivery limitation

The session prompt requests `master_chat_work/20261030_upgrade2/S9_external/`, but that directory did not exist (`ls -ld .../S9_external` returned “No such file or directory”) and the session's writable root is `.../S9_external_research/` (environment permission profile). The files are in the writable root. **Recommendation 4:** Have the master read them from `S9_external_research/` or copy them to the requested destination from a session with write access. Expected gain: the master receives the completed artifacts. Risk: downstream tooling may look only for `S9_external/`. Verify by resolving all six deliverable paths before aggregation.
