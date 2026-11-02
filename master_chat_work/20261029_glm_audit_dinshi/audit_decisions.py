# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
# How to run: imported by audit_report.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: str
    reason: str
    effect: str
    fix: str


DECISIONS = {
    '072aced5': Decision('UNCLEAR', 'No captured app outputs and three trailing empty agent steps; the termination cause is not recorded.',
                        'Unknown; zero is explained by missing work, but whether the abort was model or infrastructure caused is not established. A hypothetical successful rerun could move either channel, up to 100 combined points.',
                        'Recover original provider/agent termination and sandbox logs; rerun only if the empty-response abort was external.'),
    '0b27b9dc': Decision('VALID', 'Substantial completed work, populated artifacts and nonzero criterion-level grading; rewards agree.', 'No demonstrated infrastructure score effect.', 'None established.'),
    '11564348': Decision('VALID', 'Completed work and populated artifacts; the 0.01 reward difference follows the two rounding paths.', 'Only 0.01-point reporting-rounding difference.', 'None required.'),
    '56fe3bdd': Decision('VALID', 'The agent explicitly admitted incompletion; eight missing reports explain the zero test channel.', 'Zero test credit reflects the submitted work, not a demonstrated harness outage.', 'A better agent submission, not an infrastructure rerun, is needed.'),
    '5b2b0901': Decision('VALID-WITH-NOTES', 'GLM did real work, but received a 3x agent timeout multiplier and a different rubric from Opus.',
                        'No demonstrated change to GLM own score (0 points from the comparison issue); the GLM-versus-Opus gap is not controlled.',
                        'For a fair comparison, align rubric and agent budgets, then regrade/re-evaluate both models. Do not label the existing gap model ability.'),
    '65ba10c2': Decision('VALID-WITH-NOTES', 'GLM grading is numerically coherent; reward.txt is missing and Opus used older criterion coverage.',
                        'Missing text has 0-point effect because raw and percentage JSON exist; rounding differs by 0.01. The cross-model gap is not controlled.',
                        'Restore the text export from the existing JSON if desired; regrade Opus with the same tests and rubric before comparing.'),
    '69de664a': Decision('VALID', 'All positive test credit was earned; four failed negative criteria are untriggered penalties, not a crash.', 'Only 0.01-point reporting-rounding difference.', 'None required.'),
    '6d12f970': Decision('UNCLEAR', 'All tests were enumerated, but broad exception-to-False wrappers hide why substantive checks failed; Opus also differs in rubric and budget.',
                        'No defensible point estimate. Holding the judge channel fixed, correcting hypothetical false test failures could add at most about 48.46 combined points; this is a ceiling, not an inferred correction.',
                        'Recover per-check exceptions and delivered-program exit/stderr logs; if absent, needs an instrumented verifier-only regrade. Align the Opus rubric/budget separately.'),
    '8764bfdd': Decision('VALID', 'Static comparison proves wrong delivered record-set digests; a passed hidden-run criterion rules out a global test-run failure.', 'No demonstrated infrastructure score effect.', 'Correct the delivered transformation logic, not the harness.'),
    'b28ebc90': Decision('VALID', 'The delivered package and outputs exist; entrypoint-related test passes show development packaging errors were recovered.', 'No demonstrated infrastructure score effect.', 'None established.'),
    'cf9b2067': Decision('VALID-WITH-NOTES', 'GLM earned full test credit, but Opus was judged with a different rubric.',
                        'No demonstrated change to GLM own score (0 points); the cross-model rubric gap is not controlled.',
                        'Regrade both trajectories using identical rubric criteria before comparing rubric or combined scores.'),
    'd9e08524': Decision('UNCLEAR', 'There is genuine shipped-plan failure, but most hidden failures collapse wrong output, program failure and reference exceptions into False.',
                        'No defensible point estimate. With the judge fixed, the maximum possible upward test correction is about 47.12 combined points; actual correction is unknown.',
                        'Recover hidden-run/reference errors and per-check mismatch details; otherwise needs an instrumented verifier-only regrade.'),
    'daaca581': Decision('UNCLEAR', 'One visible-plus-hidden semantic check passed, but other checks suppress exceptions and leave wrong-output versus verifier-error causes unobservable.',
                        'No defensible point estimate. Holding the judge fixed, the maximum possible upward test correction is about 47.95 combined points; this is not a claimed correction.',
                        'Recover per-check failures and subprocess diagnostics; otherwise needs an instrumented verifier-only regrade.'),
    'dad47963': Decision('INVALID-VERIFIER', 'Raw reward used aggregation weights for different denominators: 12.83 conflicts with the correctly normalized 29.54 report.',
                        'The known aggregation defect depresses exported reward by 16.71 percentage points. Wrong shipped metrics are independently real; hidden-run failure causes remain unverified.',
                        'Reaggregate the existing criteria with intended weights and synchronize reward files. Recover hidden-run diagnostics before declaring the entire test channel reliable.'),
    'f357cd96': Decision('VALID', 'Completed artifacts and identical test-channel totals across models; rubric differences are recorded criterion decisions.', 'No demonstrated infrastructure score effect.', 'None established.'),
    'fb91cc7f': Decision('VALID', 'Completed work, captured outputs/data and coherent partial test credit; high rubric credit is supported by recorded reasoning.', 'No demonstrated infrastructure score effect.', 'None established.'),
}

C4_NOTES = {
    '072aced5': 'Actual zero-score cause: none of the 14 required app captures exists. This is missing output, not evidence of zero test collection. Why the agent stopped is unknown.',
    '56fe3bdd': 'Actual zero-score cause: the finish call says "I was unable to complete the task" and reports untrustworthy draft output. Only evalctl.py was captured; eight reports failed capture. This is agent incompletion. The 35 criteria include 31 positive failures and four untriggered negative criteria.',
    '6d12f970': 'Actual recorded cause of 3.09%: only deliverable format, report schemas and partition conservation passed (3/97 weight); every substantive reference/generalisation criterion failed. WRONG output versus reference/program exception is COULD NOT CHECK: tests/test_output.py:3307-3314 executes check() then catches Exception and returns False. The 600-second invocation limit is at :2422-2461; the roughly 94-second recorded verifier window does not support a full 600-second timeout. A trajectory renamed-files probe exited 1, but that is not the verifier subprocess log.',
    '8764bfdd': 'Actual cause of 5.34%: six structure checks plus concept_c9_config earned 11/206; all 15 family, 15 decoy and nine other concept checks failed. Independent static digest comparison found 60 of 62 profile/set digests wrong (extra_evidence.json static_set_digests), using only literal expected data and delivered JSON. tests/test_output.py:271-284 compares those visible digests; :534-539 requires both visible and hidden success for C9. This supports WRONG output, not global collection/import/timeout failure. Individual hidden stderr is still unavailable.',
    'd9e08524': 'Actual recorded cause of 5.76%: three shipped structure/derivation checks plus trap_backref_deps earned 8/139. shipped_workspaces_are_settled failed. tests/test_output.py:2104-2129 compares scenario, bottleneck and performance plan values. However :1943-1976 collapses timeout/nonzero/OSError into None and :2021-2035 can cache reference exceptions. Which cause accounts for each of the many hidden failures is COULD NOT CHECK; no blanket crash or blanket correctness claim is justified.',
    'daaca581': 'Actual recorded cause of 4.11%: only feeder_balance_shape and t10_encoding_and_line_endings passed (6/146). tests/test_output.py:6691-6699 checks visible values, then a hidden run, and catches every Exception as False; :6651-6688 compares exact focused values. The passed T10 proves at least one visible-plus-hidden evaluation succeeded, ruling out total collection failure, but does not distinguish every other wrong value from a swallowed verifier exception. COULD NOT CHECK individual causes without logs.',
    'dad47963': 'Actual cause of the visible 6.45% failures includes WRONG output: only existence/schema/layout/reconciliation pass (6/93); eight of nine report texts differ from literal expected data. population_summary.json:4 has accounts 26882 versus 27675; discrimination.json:4 has AUC 0.684198 versus 0.680606 (extra_evidence.json static_output_differences, sourced from tests/test_output.py:36 PAYLOAD). _shipped_exact at :67-68 compares those texts directly. Hidden engine stderr is sent to DEVNULL at :184 and timeout/nonzero runs return failure at :165-201, so their individual causes remain COULD NOT CHECK. The separate aggregation defect is C6.',
}

C8_NOTES = {
    '5b2b0901': 'Different rubric: positive weight 35 for GLM versus 43 for Opus; GLM has additional early-runnable/time-limit criteria and lower headline weights. result.json $.config.agent_timeout_multiplier is 3.0 for GLM versus null for Opus. This is not a controlled budget or rubric comparison.',
    '65ba10c2': 'Different tests and rubric: 34/68 positive test criteria-weight coverage versus Opus 33/67; GLM includes core_documents_line_endings. Positive rubric denominator is 91 versus Opus 86, with split and additional criteria. Regrade Opus before attributing the gap to ability.',
    '6d12f970': 'Both test channels are 3.09, but positive rubric denominators are 32 versus 34, with changed questions/weights. GLM agent_timeout_multiplier is 3.0 versus Opus null. Neither the rubric gap nor elapsed effort is controlled.',
    'cf9b2067': 'Positive rubric denominator is 16 for GLM versus 15 for Opus, with 10 versus nine criteria and changed content. GLM full test credit is genuine on the recorded criteria, but the combined gap is not a like-for-like rubric comparison.',
}
