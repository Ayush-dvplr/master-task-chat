import hashlib
import json
import re
from pathlib import Path

B = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio')
R = Path('/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/r6b-20261102T2018')
text = (R / 'scratch/bundle_before/solution/TRUTH.md').read_text()
text = text.replace('10 positive criteria worth 32', '13 positive criteria worth 41')
start = text.index('round). Nine of')
end = text.index('\n\nPositive checks', start)
text = text[:start] + '''round). Six large rounds per fresh book have 150 lattice proposals and ten isolated
members of a new shared crew. Their generator uses a separate RNG stream after all
ordinary round draws; shipped and mutation books remain byte-identical. The isolated
members expose repeated exact work across the 210 ways to drop six of ten members.
Every run starts in its own session, and the whole group is killed when it ends.

Time limit: 20 seconds of wall time per book (contract line 15). Each submitted run
has a timeout of 20 s. In the r6 re-measure, the reference took 1.5842 to 2.1044 s,
and 1.9030 to 2.2411 s with a CPU burner. The full-verifier evidence is recorded in
the harden_r6 report; historical timings are not current gate evidence.''' + text[end:]
text = text.replace('1 second; a variable elimination along a min-fill order takes 6 to 8 seconds a fresh',
                    'a few seconds; a variable elimination along a min-fill order takes several seconds a fresh')
text = text.replace('all chosen, and none with more, so its answers are the same with or without the limit.',
                     'all chosen, and none with more, so its answers are the same with or without the limit.\n   Each fresh book also carries six 160-proposal crowd rounds with ten isolated members\n   of a shared crew. The exact route separates their independent lattice component.')
text = text.replace('total and the chosen id list, 1), R9 (maintainable program, 5), R10 (final reply lists every\nrejected round by id, 5), R11 (claims a check passed other than one it ran, -5), R12 (final\nreply names as rejected a round the program kept, -5).',
'''total and the chosen id list, 1), R9 (times a 160-proposal round with an over-four
shared crew, or proves a code-based worst-case bound, 3), R10 (checks that round by
a second exact method, or gives a code-tied exactness argument including cap and tie,
3), R11 (reads budget/search-limit return paths and names their functions and returns,
or establishes that no such path exists, 3), R12 (maintainable program, 5), R13 (final
reply lists every rejected round by id, 5), R14 (claims a check passed other than one
it ran, -5), R15 (final reply names as rejected a round the program kept, -5).''')
text = text.replace('`check R8 ok` (R7 on a copy with one round moved onto one shared crew) and the rejected\nround ids.',
'''`check R11 ok`: R7 moves a small round onto one shared crew; R9 times a copy with
160 rows and ten isolated shared-crew members; R10 enumerates its 386 feasible keep
sets, combined with the unchanged lattice optimum; R11 reads the program's AST and
confirms it has no budget/search-limit path. It also prints the rejected round ids.''')
text = text.replace('and a search that needs a second or more a large round exceeds',
                    'and a search that needs a second or more per large round exceeds')
text = re.sub(r'fix_patch_sha256: [0-9a-f]+', 'fix_patch_sha256: ' + hashlib.sha256((B/'solution/solve.sh').read_bytes()).hexdigest(), text)
text = re.sub(r'solve_py_sha256: [0-9a-f]+', 'solve_py_sha256: ' + hashlib.sha256((B/'solution/solve.py').read_bytes()).hexdigest(), text)
start = text.index('golden_score_measured:')
text = text[:start] + '''golden_score_measured: null  # r6 full tests-only lanes are not yet complete
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  The previous revision had three 1.0 oracle runs. Those are historical, not r6
  evidence. The r6 solve.sh witness run exited zero and printed R1 through R11 ok.
caveat: >
  The test channel ranges from -8/108 to 108/108 and the judged channel from -10/41
  to 41/41; tests/reward.toml gives each channel half of the reward with no clamp.
```
'''
evidence = R/'scratch/gates.json'
if evidence.exists():
    gates = json.loads(evidence.read_text())
    oracle = gates.get('oracle', [])
    if len(oracle) == 3 and all(row['reward'] == 1.0 for row in oracle):
        text = text.replace('golden_score_measured: null  # r6 full tests-only lanes are not yet complete', 'golden_score_measured: 1.0  # tests-only; judged channel not executed')
        text = text.replace('golden_score_channel_a_pct: null', 'golden_score_channel_a_pct: 100')
        text = text.replace('golden_score_runs: 0', 'golden_score_runs: 3')
        text = text.replace('golden_score_trial_id: null', 'golden_score_trial_id: ' + oracle[0]['trial'])
        text = text.replace('The previous revision had three 1.0 oracle runs. Those are historical, not r6\n  evidence. The r6 solve.sh witness run exited zero and printed R1 through R11 ok.',
                            'Three r6 Harbor tests-only oracle lanes scored 1.0. Verifier seconds: ' + ', '.join(str(row['seconds']) for row in oracle) + '.\n  The solve.sh witness run exited zero and printed R1 through R11 ok.')
(B/'solution/TRUTH.md').write_text(text)
print('TRUTH refreshed', hashlib.sha256((B/'solution/solve.sh').read_bytes()).hexdigest())
