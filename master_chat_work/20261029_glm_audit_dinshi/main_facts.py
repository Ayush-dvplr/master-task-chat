# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
# How to run: python3 -B main_facts.py
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import tomllib
from collections import Counter
from pathlib import Path

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None
ROOT = Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
OUT = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_glm_audit_dinshi')


def load(path: Path) -> JSON:
    return json.loads(path.read_text()) if path.is_file() else None


def object_value(value: JSON) -> dict[str, JSON]:
    assert isinstance(value, dict), type(value)
    return value


def array(value: JSON) -> list[JSON]:
    assert isinstance(value, list), type(value)
    return value


def trajectory(path: Path) -> dict[str, JSON]:
    data = object_value(load(path))
    steps = [object_value(s) for s in array(data['steps'])]
    agents = [(i, s) for i, s in enumerate(steps) if s['source'] == 'agent']
    calls = [(i, object_value(c)) for i, s in enumerate(steps) for c in array(s.get('tool_calls') or [])]
    patterns = re.compile(r'Traceback|rate.limit|RateLimit|context.{0,15}(?:exceed|overflow)|APIError|BadRequest|InternalServerError|ServiceUnavailable|timed out|command not found|Permission denied|exit (?:code )?137|out of memory|no module named|no such file', re.I)
    hits: list[JSON] = []
    for i, step in enumerate(steps):
        material = json.dumps({'message': step.get('message'), 'observation': step.get('observation')})
        matches = list(patterns.finditer(material))
        if matches:
            hits.append({'index': i, 'step_id': step['step_id'], 'source': step['source'], 'excerpts': [material[max(0, m.start()-110):m.end()+220] for m in matches[:6]]})
    return {
        'steps': len(steps), 'sources': dict(Counter(str(s['source']) for s in steps)),
        'calls': len(calls), 'tools': dict(Counter(str(c['function_name']) for _, c in calls)),
        'first': steps[0], 'last': steps[-1],
        'last_agent_index': agents[-1][0], 'last_agent': agents[-1][1],
        'final_metrics': data.get('final_metrics'), 'error_hits': hits,
        'empty_agent_indices': [i for i, s in agents if not s.get('message') and not s.get('tool_calls')],
    }


def run_facts(path: Path) -> dict[str, JSON]:
    result = object_value(load(path / 'result.json'))
    score = object_value(load(path / 'verifier/score.json'))
    detail_data = load(path / 'verifier/reward-details.json')
    detail = object_value(detail_data) if detail_data is not None else {}
    components = array(object_value(detail['reward']).get('components') or []) if detail else []
    compact: list[JSON] = []
    for component in components:
        c = object_value(component)
        d = object_value(c['detail'])
        criteria = [object_value(v) for v in array(d.get('criteria') or [])]
        positive = sum(float(str(v['weight'])) for v in criteria if float(str(v['weight'])) > 0)
        weighted = sum(float(str(v['weight'])) * float(str(v['value'])) for v in criteria)
        compact.append({'name': c['name'], 'weight': c['weight'], 'score': d['score'], 'positive_weight': positive, 'weighted_sum': weighted, 'criteria': criteria, 'keys': list(d), 'judge': d.get('judge'), 'error': d.get('error')})
    manifest = array(load(path / 'artifacts/manifest.json'))
    manifest_facts: list[JSON] = []
    for i, entry in enumerate(manifest):
        e = object_value(entry)
        dest = e.get('destination')
        local = path / str(dest) if dest else path / '__missing__'
        manifest_facts.append({'index': i, 'source': e['source'], 'destination': dest, 'status': e['status'], 'exists': local.exists(), 'bytes': local.stat().st_size if local.is_file() else None})
    ctrf = object_value(object_value(load(path / 'verifier/ctrf.json'))['results'])
    report = object_value(load(path / 'report.json'))
    return {
        'summary': load(path.parent / 'pass_summary.json'),
        'config': load(path / 'config.json'), 'result': result,
        'score_top': {k: v for k, v in score.items() if k != 'rubric'},
        'reward': load(path / 'verifier/reward.json'), 'raw': load(path / 'verifier/reward_raw.json'),
        'reward_txt': (path / 'verifier/reward.txt').read_text() if (path / 'verifier/reward.txt').is_file() else None,
        'stdout': (path / 'verifier/test-stdout.txt').read_text() if (path / 'verifier/test-stdout.txt').is_file() else None,
        'verifier_files': sorted(p.name for p in (path / 'verifier').iterdir()),
        'components': compact, 'ctrf_summary': ctrf['summary'], 'ctrf_tests': ctrf['tests'],
        'report_pytest': report.get('pytest'), 'report_top': {k: v for k, v in report.items() if k not in {'pytest', 'rubric'}},
        'usage': load(path / 'trajectory_usage.json'), 'manifest': manifest_facts,
        'app_exists': (path / 'artifacts/app').is_dir(),
        'app_files': [{'path': str(p.relative_to(path)), 'bytes': p.stat().st_size} for p in sorted((path / 'artifacts/app').rglob('*')) if p.is_file()],
        'trajectory': trajectory(path / 'agent/trajectory.json'),
    }


def main() -> None:
    with (OUT / 'tasks.csv').open(newline='') as handle:
        ids = [row['task'] for row in csv.DictReader(handle)]
    facts: dict[str, JSON] = {}
    for task in ids:
        task_path = ROOT / task
        env = dict(os.environ, GIT_MASTER='1', GIT_OPTIONAL_LOCKS='0')
        history = subprocess.run(['git', 'log', '-1', '--format=%H %ci %s', '--', task], cwd=ROOT, env=env, check=True, text=True, capture_output=True).stdout.strip()
        history_bundle = subprocess.run(['git', 'log', '-1', '--format=%H %ci %s', '--', f'{task}/task.toml', f'{task}/instruction.md', f'{task}/tests', f'{task}/environment', f'{task}/solution'], cwd=ROOT, env=env, check=True, text=True, capture_output=True).stdout.strip()
        with (task_path / 'tests/reward.toml').open('rb') as handle:
            reward_config = tomllib.load(handle)
        with (task_path / 'task.toml').open('rb') as handle:
            task_config = tomllib.load(handle)
        facts[task] = {'history': history, 'bundle_history': history_bundle, 'reward_config': reward_config, 'task_config': task_config, 'instruction': (task_path / 'instruction.md').read_text(), 'glm-5.3': run_facts(task_path / 'trajectories/glm-5.3/run_1'), 'claude-opus-5': run_facts(task_path / 'trajectories/claude-opus-5/run_1')}
        print(task, 'parsed both recorded models')
    (OUT / 'main_facts.json').write_text(json.dumps(facts, indent=2) + '\n')


if __name__ == '__main__':
    main()
