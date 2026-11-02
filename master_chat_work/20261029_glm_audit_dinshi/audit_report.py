# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
# How to run: python3 -B audit_report.py
from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict

from audit_checks import checks_for, quote
from audit_decisions import DECISIONS
from main_facts import OUT, JSON, array, load, object_value


def main() -> None:
    facts = object_value(load(OUT / 'main_facts.json'))
    extra = object_value(load(OUT / 'extra_evidence.json'))
    with (OUT / 'tasks.csv').open(newline='') as handle:
        inventory = list(csv.DictReader(handle))
    assert len(facts) == len(inventory) == 16
    rows = [row for task, value in facts.items() for row in checks_for(task, object_value(value), object_value(extra[task]))]
    assert len(rows) == 128
    with (OUT / 'checks.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=('task', 'check', 'result', 'evidence'))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    verdicts = {task: DECISIONS[task[:8]].verdict for task in facts}
    counts = Counter(verdicts.values())
    limits: list[JSON] = [{'task': row.task, 'check': row.check, 'reason': row.evidence} for row in rows if row.result == 'COULD NOT CHECK']
    limits.extend([
        {'tasks': list(facts), 'check': 'C4', 'reason': 'COULD NOT CHECK individual hidden-test subprocess stderr/exit reasons or historical image build health: test-stdout.txt contains only a reward line; no Docker/harness/task code was run. Needs original per-check diagnostics or an instrumented verifier regrade.'},
        {'tasks': list(facts), 'check': 'C2/C7', 'reason': 'COULD NOT CHECK provider-side model identity, billing totals or original memory/OOM/termination events beyond recorded trajectory and result fields. Needs provider and original sandbox logs; opaque Bedrock profile names are not independent identity attestation.'},
        {'tasks': list(facts), 'check': 'C8/C6', 'reason': 'All Opus reward.txt files are absent (main_facts.json $[task]["claude-opus-5"].reward_txt=null). reward_raw.json is additionally absent for 56fe, 8764 and daa (the corresponding .raw=null). COULD NOT CHECK absent exports; available reward.json/report/score/summary percentages remain comparable within rounding. Needs the original exports to verify those missing relationships.'},
        {'tasks': ['56fe3bdd-00c6-5b13-a5c8-90a94ccc475e', '8764bfdd-69b5-57a0-bc6a-db095fe071db', 'daaca581-de32-5fc7-bd44-dd51c8f26be3'], 'check': 'C8', 'reason': 'Opus trajectory_usage.json is absent (main_facts.json $[task]["claude-opus-5"].usage=null); token metrics can be read in trajectory/result, but the separate usage/cost export cannot be compared.'},
        {'check': 'Audit tooling', 'reason': 'Python LSP diagnostics unavailable: basedpyright is not installed and installation was previously declined. Helper scripts were executed as file-only analysis and syntax-compiled in memory instead.'},
    ])
    dad = next(task for task in facts if task.startswith('dad47963'))
    result = {'status': 'DONE', 'tasks': len(facts), 'verdicts': verdicts,
              'invalid': [{'task': dad, **asdict(DECISIONS['dad47963'])}],
              'mismatches': [{'task': dad, 'type': 'reward-aggregation', 'exported_reward': 12.83, 'summary_combined': 29.54, 'difference_points': 16.71, 'evidence': f'{dad}/trajectories/glm-5.3/run_1/verifier/reward-details.json:$.reward.components[0].weight=0.00980392156862745; components[1].weight=0.005050505050505051; reward.json:$.reward=12.83; score.json:$.final_reward=29.54; tests/reward.toml:4 judge=0.02631578947368421,test_output=0.005376344086021506'}],
              'could_not_check': limits}
    (OUT / 'result_b118b8c.json').write_text(json.dumps(result, indent=2) + '\n')
    text = ['# GLM-5.3 Dinshi Audit: b118b8c', '',
            'Read-only, on-disk audit. No Docker, harness, task code, verifier functions, network requests or git mutations were run. All analysis outputs are confined to this output directory. Main-chat-only execution was followed after the user requested it.', '',
            'Source paths beginning with a UUID are relative to `/Users/mac/Desktop/Terminal Bench/anubis-stage-2/`. `main_facts.json` and `extra_evidence.json` are reproducible audit snapshots in OUT, not model outputs. JSON paths are zero-indexed. Exact quoted excerpts are explicitly marked. `HARNESS` denotes the local read-only reference checkout identified in SCORING.md.', '',
            '## Verdicts', '',
            '| task id | co-author | GLM tests/rubric/combined | verdict | one-line reason | evidence file:line or JSON path |',
            '|---|---|---|---|---|---|']
    for record in inventory:
        task = record['task']
        f = object_value(facts[task])
        g = object_value(f['glm-5.3'])
        s = object_value(g['summary'])
        decision = DECISIONS[task[:8]]
        score = '/'.join(str(s[k]) for k in ('average_test_weights_percentage', 'average_rubric_weights_percentage', 'average_combined_score'))
        evidence = f'`{task}/trajectories/glm-5.3/pass_summary.json:$.per_run[0]` = `{quote(array(s["per_run"])[0])}`; reason evidence in C1-C8 below'
        text.append(f'| {task} | {record["co_author"]} | {score} | **{decision.verdict}** | {decision.reason} | {evidence} |')
    text.extend(['', 'Counts: ' + ', '.join(f'{key}={value}' for key, value in sorted(counts.items())) + '. INVALID-INFRA=0; STALE=0.', '',
                 'VALID means the recorded evidence supports the score as real agent work, not that an unperformed runtime replay was certified. VALID-WITH-NOTES issues have no demonstrated >5-point effect on GLM own score; they can still invalidate a cross-model comparison. UNCLEAR is used where the missing cause could materially change the result. No unsupported infrastructure or stale-bundle verdict is inferred from a low score alone.', '',
                 '## Inventory And Scoring', '',
                 'Re-derived all task.toml authors lists case-insensitively: exactly the supplied 16 task IDs, no added or missing IDs. `tasks.csv` gives each authors-line citation and quote; its `inventory_difference` is `none` for every row. `SCORING.md` reconstructs the 50/50 channel normalization, signed negative criteria and distinct rounding paths. All 32 pass summaries have one run (`main_facts.json:$[task][model].summary.runs = 1`).', '',
                 'The one demonstrated substantive number mismatch is dad47963: `reward.json:$.reward = 12.83` versus `score.json:$.final_reward = 29.54`, explained by different aggregation weights, not by rounding. Other 0.01 differences are expected. Missing reward.txt does not imply missing reward.json.', '',
                 '## Per-Task Checks', ''])
    names = {'C1': 'Run Completed', 'C2': 'Agent Really Worked', 'C3': 'Output Exists', 'C4': 'Tests Ran Honestly', 'C5': 'Judge Ran Honestly', 'C6': 'Numbers Agree', 'C7': 'Same Bytes', 'C8': 'Fair Against Opus'}
    for record in inventory:
        task = record['task']
        decision = DECISIONS[task[:8]]
        text.extend([f'### {task}', '', f'**{decision.verdict}**. {decision.reason}', '', f'Estimated effect: {decision.effect}', '', f'What would fix it: {decision.fix}', ''])
        for row in rows:
            if row.task == task:
                text.extend([f'#### {row.check} {names[row.check]}: {row.result}', '', row.evidence, ''])
    text.extend(['## Cross-Task Patterns', '',
                 '- **Real failure is not automatically infrastructure failure.** 56fe explicitly says it could not complete, and only its draft program was captured. 072 is different: its last three agent steps are empty and all required app captures failed, without a recorded explanation. Evidence: each task C2-C3 and `main_facts.json:$[task]["glm-5.3"].trajectory.last_agent` / `.manifest`.',
                 '- **Low tests/high rubric often reflects process versus product.** 8764 has 60 of 62 wrong static record-set digests (`extra_evidence.json:$["8764bfdd-69b5-57a0-bc6a-db095fe071db"].static_set_digests[*].equal`); dad has eight of nine wrong report texts (`extra_evidence.json:$["dad47963-3ef5-569b-9c83-dcf0fa4ffb57"].static_output_differences[*].equal`). Neither high process rubric establishes correct output. 6d12/d9e/daa retain material uncertainty because their wrappers suppress distinct failure causes; see C4 source lines.',
                 '- **Postprocessing and regrades matter.** Eleven GLM result files have source_trial.action="regrade" and null agent_execution, while the saved trajectory predates the regrade. These timestamps cannot measure original agent runtime (per-task C1). Raw 0-1 reward and rescaled percentage export are different scales; 0.01 double-rounding differences are normal (SCORING.md).',
                 '- **One known numerical defect.** dad uses raw aggregation weights 0.5/51 and 0.5/99, not the intended 0.5/19 and 0.5/93. This explains the 16.71-point export discrepancy. Those weights equal f357 current weights, but the copying mechanism is not on disk (SCORING.md and dad C6).',
                 '- **Four comparisons are not rubric-aligned.** 5b2b, 65ba, 6d12 and cf9 have different GLM/Opus rubric signatures (`extra_evidence.json:$[task].rubric_same_between_models = false`). 65ba also differs in test coverage; 5b2b and 6d12 GLM result configs have agent_timeout_multiplier=3.0 versus Opus null. These gaps cannot be attributed solely to model ability (C8).',
                 '- **Historical bytes remain unproven, not proven stale.** Every current instruction occurs in both saved user prompts (`extra_evidence.json:$[task].models[model].instruction_matches_current = true`), but git history is newer than the run and the stored hash has no original bundle to compare. Import/metadata commits are not evidence that substantive bytes changed (C7).', '',
                 '## COULD NOT CHECK', '',
                 'The following are deliberately unresolved. No runtime checks were attempted. For every C7 item, the required evidence is an archived original task bundle or TrialLock/file digest manifest; for swallowed C4 failures, original per-check errors/exit/stderr or an instrumented verifier-only regrade; for 072 termination, original provider/agent/sandbox termination logs.', ''])
    for item in limits:
        entry = object_value(item)
        if 'task' in entry:
            matching = next(row for row in rows if row.task == entry['task'] and row.check == entry['check'])
            text.append(f'- `{entry["task"]}` {entry["check"]}: COULD NOT CHECK. See the cited evidence in its C1-C8 section above and checks.csv; ' + ('needs archived original bytes/digests.' if entry['check'] == 'C7' else 'needs missing original diagnostic/export records or a verifier-only regrade.'))
        else:
            text.append('- ' + str(entry['reason']))
    text.extend(['', '## Validation', '',
                 'Deliverables contain 16 inventory rows, 128 distinct C1-C8 rows, 16 verdicts and one substantive numeric mismatch. Report generation executed only the audit helpers, not the source tasks. Python helper syntax was compiled in memory; no bytecode was written into the source repository. LSP validation could not run because basedpyright is not installed and installation was previously declined. See result_b118b8c.json for machine-readable decisions and unresolved items.', ''])
    (OUT / 'AUDIT.md').write_text('\n'.join(text))
    print('Wrote checks.csv, AUDIT.md and result_b118b8c.json:', dict(counts))


if __name__ == '__main__':
    main()
