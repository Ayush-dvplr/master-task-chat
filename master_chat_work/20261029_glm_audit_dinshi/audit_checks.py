# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
# How to run: imported by audit_report.py
from __future__ import annotations

import json
from dataclasses import dataclass

from audit_decisions import C4_NOTES, C8_NOTES
from main_facts import JSON, array, object_value


@dataclass(frozen=True, slots=True)
class Check:
    task: str
    check: str
    result: str
    evidence: str


def quote(value: JSON) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'))


def ref(path: str, key: str, value: JSON) -> str:
    return f'`{path}:{key}` = `{quote(value)}`'


def checks_for(task: str, facts: dict[str, JSON], extra: dict[str, JSON]) -> list[Check]:
    prefix = task[:8]
    g = object_value(facts['glm-5.3'])
    o = object_value(facts['claude-opus-5'])
    r = object_value(g['result'])
    rc = object_value(r['config'])
    tr = object_value(g['trajectory'])
    models = object_value(extra['models'])
    gx = object_value(models['glm-5.3'])
    ox = object_value(models['claude-opus-5'])
    base = f'{task}/trajectories/glm-5.3/run_1/'
    opus = f'{task}/trajectories/claude-opus-5/run_1/'
    source = base + 'result.json'
    derived = f'main_facts.json:$["{task}"]["glm-5.3"]'
    xref = f'extra_evidence.json:$["{task}"]'
    rows: list[Check] = []
    lifecycle = '; '.join(ref(source, '$.' + key, r[key]) for key in ('started_at', 'finished_at', 'agent_execution', 'verifier', 'environment_setup', 'agent_setup', 'step_results', 'exception_info'))
    lifecycle += '; ' + ref(source, '$.agent_result', r['agent_result'])
    action = rc.get('source_trial')
    if action:
        lifecycle += '; ' + ref(source, '$.config.source_trial.action', object_value(action)['action']) + '. These are regrade timestamps, not the original agent runtime.'
    lifecycle += ' Verifier finish and criteria artifacts are present; null exception_info alone was not treated as proof of success.'
    lifecycle += ' Original stop/kill cause is not established.' if prefix == '072aced5' else ' The recorded final agent step is a finish call or substantive closing response (C2), not an observed forced kill.'
    rows.append(Check(task, 'C1', 'COULD NOT CHECK' if prefix == '072aced5' else 'PASS', lifecycle))

    last = object_value(tr['last_agent'])
    last_index = tr['last_agent_index']
    c2 = f'{derived}.trajectory.steps = `{tr["steps"]}`; .calls = `{tr["calls"]}`; .empty_agent_indices = `{quote(tr["empty_agent_indices"])}`. '
    message = str(last.get('message') or '')
    c2 += ref(base + 'agent/trajectory.json', f'$.steps[{last_index}].message', message[:300]) + (' (exact excerpt)' if len(message) > 300 else '')
    calls = array(last.get('tool_calls') or [])
    if calls:
        call = object_value(calls[0])
        c2 += '; ' + ref(base + 'agent/trajectory.json', f'$.steps[{last_index}].tool_calls[0].function_name', call['function_name'])
        args = call.get('arguments')
        c2 += '; ' + ref(base + 'agent/trajectory.json', f'$.steps[{last_index}].tool_calls[0].arguments', args)
    usage = object_value(array(g['usage'])[0])
    c2 += '; ' + '; '.join(ref(base + 'trajectory_usage.json', '$[0].' + k, usage[k]) for k in ('model_name', 'trajectory_input_tokens', 'trajectory_input_cache_tokens', 'trajectory_output_tokens', 'trajectory_cost_usd'))
    c2 += f'. {derived}.trajectory.error_hits has `{len(array(tr["error_hits"]))}` flagged development/probe steps; these were reviewed as context, not equated with provider failures. No explicit terminal API/rate-limit/context/OOM event was established from the recorded messages. Cost null/agent_result cost 0 is not proof of free usage.'
    if prefix == '072aced5':
        c2 += ' Steps 18, 19 and 20 have empty messages and no tool calls; no completion response exists. COULD NOT CHECK why replies became empty.'
    rows.append(Check(task, 'C2', 'COULD NOT CHECK' if prefix == '072aced5' else 'PASS', c2))

    app = [object_value(v) for v in array(g['app_files'])]
    manifest = [object_value(v) for v in array(g['manifest'])]
    app_entries = [v for v in manifest if str(v['source']).startswith('/app/')]
    failed = [v for v in app_entries if v['status'] != 'ok']
    c3 = f'{derived}.app_exists = `{quote(g["app_exists"])}`; .app_files contains `{len(app)}` files, all present files have positive byte sizes; {xref}.models["glm-5.3"].empty_artifacts = `{quote(gx["empty_artifacts"])}`. '
    c3 += '; '.join(ref(base + 'artifacts/manifest.json', f'$[{v["index"]}].source', v['source']) + '; ' + ref(base + 'artifacts/manifest.json', f'$[{v["index"]}].status', v['status']) for v in app_entries)
    c3 += f'. Required output paths were compared with `{task}/instruction.md` and `task.toml` artifacts; exact output instruction lines and file sizes are retained in {xref}.models["glm-5.3"].instruction_output_lines and {derived}.app_files.'
    if prefix == '5b2b0901':
        c3 += ' Only gate.py is the declared captured deliverable, not a missing set of report files.'
    if prefix == 'fb91cc7f':
        c3 += ' The capture includes /app/data as well as /app/out; 44 is not a claim of 44 output reports. Dynamic partition completeness is limited to recorded artifact tests.'
    rows.append(Check(task, 'C3', 'FAIL' if failed or not g['app_exists'] else 'PASS', c3))

    c4 = ref(base + 'verifier/ctrf.json', '$.results.summary', g['ctrf_summary'])
    c4 += '; ' + ref(base + 'verifier/test-stdout.txt', '1', str(g['stdout']).rstrip('\n'))
    c4 += f'; {xref}.models["glm-5.3"].test_error_statuses = `{quote(gx["test_error_statuses"])}`. These are rewardkit criterion counts; zero statuses named error is not proof that no exception was swallowed. Negative failed criteria are untriggered penalties, not ordinary failed pytest tests. '
    c4 += C4_NOTES.get(prefix, 'The criterion collection is nonempty with both positive passes and substantive failures (or all positive passes); there is no recorded collection/import/plugin/container/OOM/exit-137 failure. Failing positive criteria are listed below. Their individual hidden subprocess diagnostics were not retained, so absence of an explicit infra error is not a runtime replay guarantee.')
    c4 += ' Failed positive criteria: ' + quote(gx['test_positive_failed']) + '.'
    rows.append(Check(task, 'C4', 'COULD NOT CHECK' if prefix in ('6d12f970', 'd9e08524', 'daaca581') else 'PASS', c4))

    comp = [object_value(v) for v in array(g['components'])]
    judge = comp[0]
    criteria = [object_value(v) for v in array(judge['criteria'])]
    first = criteria[0]
    c5 = ref(base + 'verifier/reward-details.json', '$.reward.components[0].detail.score', judge['score'])
    c5 += f'; {derived}.components[0].positive_weight = `{judge["positive_weight"]}`; .error = `{quote(judge["error"])}`; {xref}.models["glm-5.3"].rubric_empty_replies = `{quote(gx["rubric_empty_replies"])}`. All `{len(criteria)}` recorded criteria have reasoning, and their IDs/descriptions/weights match the current judge.toml; no skipped/default/API-error rubric was found. '
    c5 += ref(base + 'verifier/reward-details.json', '$.reward.components[0].detail.criteria[0].reasoning', first['reasoning'])
    c5 += '; ' + ref(base + 'verifier/score.json', '$.judge_model', object_value(g['score_top'])['judge_model'])
    if prefix in ('072aced5', '56fe3bdd'):
        c5 += ' Missing outputs were not silently credited as complete: 072 has zero judge credit; 56fe positive credit is for observed process, while final correctness/completion criteria fail. See complete criteria/reasoning in the cited JSON.'
    c5 += ' A high process rubric is not a claim that the deterministic output values passed.'
    rows.append(Check(task, 'C5', 'PASS', c5))

    st = object_value(g['score_top'])
    summ = object_value(g['summary'])
    c6 = '; '.join((ref(base + 'verifier/reward_raw.json', '$.reward', object_value(g['raw'])['reward']), ref(base + 'verifier/reward.json', '$.reward', object_value(g['reward'])['reward']), ref(base + 'verifier/reward.txt', '1', str(g['reward_txt']).strip()) if g['reward_txt'] is not None else f'{derived}.reward_txt = `null` (file absent)', ref(source, '$.verifier_result.rewards.reward', object_value(object_value(r['verifier_result'])['rewards'])['reward']), ref(base + 'verifier/score.json', '$.final_reward', st['final_reward']), ref(base + 'report.json', '$.final_reward', object_value(g['report_top'])['final_reward']), ref(f'{task}/trajectories/glm-5.3/pass_summary.json', '$.average_combined_score', summ['average_combined_score'])))
    c6 += '; raw component weights/scores: ' + quote([{k: v[k] for k in ('name', 'weight', 'score', 'positive_weight')} for v in comp])
    c6 += '. Apply SCORING.md: raw files are 0-1, text/compact JSON are percentages, report/summary average separately rounded channels. '
    if prefix == 'dad47963':
        c6 += 'FAIL: recorded judge/test weights .5/51 and .5/99 yield 12.83, not intended .5/19 and .5/93 yielding 29.54. Current tests/reward.toml:4 specifies judge=0.02631578947368421 and test_output=0.005376344086021506. The 16.71-point discrepancy is substantive; these wrong weights equal f357cd96/tests/reward.toml:4 without proving the copying mechanism.'
    else:
        c6 += 'Available numerical files agree within the explained 0.01-point rounding path.'
    rows.append(Check(task, 'C6', 'FAIL' if prefix == 'dad47963' else ('COULD NOT CHECK' if g['reward_txt'] is None else 'PASS'), c6))

    cfg = object_value(g['config'])
    c7 = '; '.join((ref(source, '$.task_checksum', r['task_checksum']), ref(source, '$.config.task.path', object_value(rc['task'])['path']), ref(base + 'config.json', '$.task.path', object_value(cfg['task'])['path']), ref(base + 'config.json', '$.agent.model_name', object_value(cfg['agent'])['model_name'])))
    c7 += f'; {xref}.models["glm-5.3"].instruction_matches_current = `{quote(gx["instruction_matches_current"])}`; .timeout_settings = `{quote(gx["timeout_settings"])}`; .agent_limits = `{quote(gx["agent_limits"])}`. '
    c7 += ref('main_facts.json', f'$["{task}"].history', facts['history']) + '; ' + ref('main_facts.json', f'$["{task}"].bundle_history', facts['bundle_history'])
    c7 += f'; current task.toml limits {ref("main_facts.json", f"$[\"{task}\"].task_config.agent", object_value(facts["task_config"]).get("agent"))}; {ref("main_facts.json", f"$[\"{task}\"].task_config.verifier", object_value(facts["task_config"]).get("verifier"))}. These git commits postdate the recorded started_at; import/metadata commits alone do not prove executable changes. COULD NOT CHECK full original byte equality: no archived original bundle/TrialLock digest is available in the run. Local HARNESS/src/harbor/models/task/task.py:198-212 hashes the whole directory, now including trajectories, so a current whole-folder hash would not be a valid old-bundle comparison. Instruction/rubric agreement does not prove environment/test bytes equal.'
    rows.append(Check(task, 'C7', 'COULD NOT CHECK', c7))

    ort = object_value(o['result'])
    c8 = ref(opus + 'result.json', '$.started_at', ort['started_at']) + '; ' + ref(opus + 'result.json', '$.finished_at', ort['finished_at']) + '; ' + ref(opus + 'result.json', '$.exception_info', ort['exception_info'])
    c8 += '; ' + ref(opus + 'verifier/ctrf.json', '$.results.summary', o['ctrf_summary'])
    c8 += '; ' + ref(f'{task}/trajectories/claude-opus-5/pass_summary.json', '$', o['summary'])
    c8 += f'; {xref}.rubric_same_between_models = `{quote(extra["rubric_same_between_models"])}`; .models["claude-opus-5"].timeout_settings = `{quote(ox["timeout_settings"])}`; .agent_limits = `{quote(ox["agent_limits"])}`. '
    ot = object_value(o['trajectory'])
    c8 += f'Opus C1-C3: {len(array(o["app_files"]))} nonempty captured app files, {ot["steps"]} steps/{ot["calls"]} tool calls, final completion step; evidence is main_facts.json:$["{task}"]["claude-opus-5"].manifest/.app_files/.trajectory/.result. Opus C4-C6: criterion counts above; no error statuses or empty rubric verdicts in {xref}.models["claude-opus-5"]; percentage/raw relationships and any 0.01 rounding differences follow SCORING.md. '
    c8 += '; '.join(ref(opus + 'result.json', '$.' + key, ort[key]) for key in ('agent_execution', 'verifier', 'agent_result', 'task_checksum')) + '; '
    c8 += ref(opus + 'verifier/reward.json', '$.reward', object_value(o['reward'])['reward']) + '; '
    c8 += ref('main_facts.json', f'$["{task}"]["claude-opus-5"].raw', o['raw']) + '; '
    c8 += ref('main_facts.json', f'$["{task}"]["claude-opus-5"].reward_txt', o['reward_txt']) + '. Opus reward.txt is absent; absence of text is not absence of its percentage JSON. '
    if o['raw'] is None:
        c8 += 'COULD NOT CHECK the raw backup relationship because reward_raw.json is also absent. '
    if not array(o['components']):
        c8 += 'Opus reward-details.json is absent; detailed judge API provenance is COULD NOT CHECK even though score.json rubric verdicts/reasons exist. '
    c8 += C8_NOTES.get(prefix, 'Recorded rubric criteria and test weights match across models; separate verifier mode and judge model agree. No infrastructure explanation for the score gap was established. Model-specific token/setup settings differ, so this is not a claim of identical resource use.')
    c8 += f' Opus C7: instruction_matches_current = `{quote(ox["instruction_matches_current"])}`, but its full historical bundle checksum is also unverified. Both modes are separate (each result.json $.verifier_environment_mode = "separate"), judge is gpt-5.6-sol and disable=false. Missing original per-check stderr, API billing identity and full historical bytes remain limitations, not assumed equalities.'
    rows.append(Check(task, 'C8', 'FAIL' if prefix in C8_NOTES else ('COULD NOT CHECK' if not array(o['components']) or prefix == '072aced5' else 'PASS'), c8))
    return rows
