# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
# How to run: python3 -B extra_evidence.py
from __future__ import annotations

import ast
import base64
import hashlib
import json
import zlib
from pathlib import Path

from main_facts import OUT, ROOT, JSON, array, load, object_value


def literal_payload(path: Path, name: str) -> dict[str, JSON]:
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    encoded = ast.literal_eval(node.value)
    assert isinstance(encoded, str)
    return object_value(json.loads(zlib.decompress(base64.b64decode(encoded))))


def static_differences(task: str) -> list[JSON]:
    source = ROOT / task / 'tests/test_output.py'
    payload = literal_payload(source, 'PAYLOAD')
    expected = object_value(payload['expected'])
    out = ROOT / task / 'trajectories/glm-5.3/run_1/artifacts/app/out'
    diffs: list[JSON] = []
    for name, want in expected.items():
        assert isinstance(want, str)
        got = (out / name).read_text()
        gl, wl = got.splitlines(), want.splitlines()
        index = next((i for i, (g, w) in enumerate(zip(gl, wl)) if g != w), min(len(gl), len(wl)))
        diffs.append({'file': name, 'equal': got == want, 'actual_sha256': hashlib.sha256(got.encode()).hexdigest(),
                      'expected_sha256': hashlib.sha256(want.encode()).hexdigest(), 'line': index + 1,
                      'actual': gl[index] if index < len(gl) else '<EOF>',
                      'expected': wl[index] if index < len(wl) else '<EOF>',
                      'expected_source': f'{task}/tests/test_output.py:36 PAYLOAD decoded as JSON $.expected[{name!r}]'})
    return diffs


def set_digests(task: str) -> list[JSON]:
    payload = literal_payload(ROOT / task / 'tests/test_output.py', '_EXPECT_B64')
    sets = object_value(payload['sets'])
    out = ROOT / task / 'trajectories/glm-5.3/run_1/artifacts/app/out'
    fields = ('volume', 'path', 'sha256', 'bytes', 'mtime', 'owner', 'class', 'action')
    docs = {p: object_value(load(out / f'profile_{p}.json')) for p in ('prod', 'dev')}
    validation = object_value(load(out / 'validation_report.json'))
    results: list[JSON] = []
    for name, value in sets.items():
        spec = object_value(value)
        recs = [str(v) for v in array(spec['recs'])]
        mask_text = str(spec['mask'])
        masks = {rid: int(mask_text[2*i:2*i+2], 16) for i, rid in enumerate(recs)}
        for prof in ('prod', 'dev'):
            entries = {str(e['origin']): e for v in array(docs[prof]['entries']) if (e := object_value(v))}
            reasons = {str(e['rec_id']): str(e['reason']) for v in array(validation[prof]) if (e := object_value(v))}
            lines: list[str] = []
            for rid in sorted(recs):
                if rid in entries:
                    line = 'E|' + json.dumps([entries[rid].get(k) for i, k in enumerate(fields) if masks[rid] >> i & 1], ensure_ascii=False)
                else:
                    line = 'X|' + reasons[rid] if rid in reasons else 'A'
                lines.append(f'{rid}={line}')
            digest = hashlib.sha256('\n'.join(lines).encode()).hexdigest()
            results.append({'set': name, 'profile': prof, 'actual_digest': digest,
                            'expected_digest': spec[prof], 'equal': digest == spec[prof],
                            'source': f'{task}/tests/test_output.py:125 _recset_digest; :48 _EXPECT_B64 decoded $.sets[{name!r}][{prof!r}]'})
    return results


def main() -> None:
    facts = object_value(load(OUT / 'main_facts.json'))
    output: dict[str, JSON] = {}
    for task, value in facts.items():
        f = object_value(value)
        runs: dict[str, JSON] = {}
        signatures: dict[str, list[JSON]] = {}
        for model in ('glm-5.3', 'claude-opus-5'):
            run = object_value(f[model])
            base = ROOT / task / 'trajectories' / model / 'run_1'
            score = object_value(load(base / 'verifier/score.json'))
            rubric = [object_value(v) for v in array(score['rubric'])]
            signatures[model] = [[r['criterion'], r['score']] for r in rubric]
            trajectory = object_value(load(base / 'agent/trajectory.json'))
            steps = [object_value(s) for s in array(trajectory['steps'])]
            tests = [object_value(s) for s in array(run['ctrf_tests'])]
            result = object_value(run['result'])
            config = object_value(result['config'])
            agent_config = object_value(config['agent'])
            agent_env = object_value(agent_config.get('env') or {})
            positive = sum(float(str(t['weight'])) for t in tests if float(str(t['weight'])) > 0)
            runs[model] = {
                'instruction_matches_current': any(str(f['instruction']).strip() in str(s.get('message')) for s in steps if s['source'] == 'user'),
                'current_instruction_sha256': hashlib.sha256(str(f['instruction']).encode()).hexdigest(),
                'test_positive_weight': positive,
                'test_positive_failed': [t for t in tests if float(str(t['weight'])) > 0 and t['status'] == 'failed'],
                'test_negative_false': [t for t in tests if float(str(t['weight'])) < 0 and t['status'] == 'failed'],
                'test_error_statuses': [t for t in tests if t['status'] not in ('passed', 'failed')],
                'rubric_positive_weight': sum(float(str(r['score'])) for r in rubric if float(str(r['score'])) > 0),
                'rubric_empty_replies': [i for i, r in enumerate(rubric) if r.get('passed') is None],
                'timeout_settings': {k: v for k, v in config.items() if 'timeout' in k},
                'agent_limits': {k: v for k, v in agent_env.items() if k in ('MAX_ITERATIONS', 'LLM_MAX_OUTPUT_TOKENS', 'LLM_NUM_RETRIES')},
                'empty_artifacts': [p for p in array(run['app_files']) if object_value(p)['bytes'] == 0],
                'instruction_output_lines': [[i, line] for i, line in enumerate(str(f['instruction']).splitlines(), 1) if '/app/out' in line],
            }
        output[task] = {'models': runs, 'rubric_same_between_models': signatures['glm-5.3'] == signatures['claude-opus-5']}
    dad = 'dad47963-3ef5-569b-9c83-dcf0fa4ffb57'
    object_value(output[dad])['static_output_differences'] = static_differences(dad)
    estate = '8764bfdd-69b5-57a0-bc6a-db095fe071db'
    object_value(output[estate])['static_set_digests'] = set_digests(estate)
    (OUT / 'extra_evidence.json').write_text(json.dumps(output, indent=2) + '\n')
    for task, value in output.items():
        print(task, 'rubric_same', object_value(value)['rubric_same_between_models'])
    print('Static payload data decoded; no task functions imported or executed.')


if __name__ == '__main__':
    main()
