import json
L = {'LV-CW-1': ['greedy','greedy_ls'], 'LV-CW-2': ['no_initial','touching_only','reset_nightly'], 'LV-CW-3': ['no_crew','naive_collapse','flow_relax','lane_by_lane']}
rows = json.load(open('tmp/rt_oracle2.json'))['rows']
fail = {}
for lv, ms in L.items():
    for m in ms:
        d = json.load(open(f'tmp/cost/{m}.json'))
        for r in d['rows']:
            if (r[1] > 0) != bool(r[2]): fail.setdefault(r[0], set()).add(lv)
out = ['# LEVERS', '', 'One row per check of tests/test_output.py. A lever id is listed when at least one wrong program for that lever (WORK/mutants/, see COST_TABLE.md) fails the check.', '', '| check | weight | levers |', '|---|---|---|']
tot = {lv: 0 for lv in L}; pos = 0
for name, w, *_ in rows:
    lv = sorted(fail.get(name, ()))
    if w > 0: pos += w
    for x in lv:
        if w > 0: tot[x] += w
    out.append(f"| {name} | {w} | {', '.join(lv) or 'none (plain rule)'} |")
out += ['', '| lever | positive weight of checks it can fail | share of 98 |', '|---|---|---|']
for lv, t in tot.items(): out.append(f'| {lv} | {t} | {100*t/pos:.0f}% |')
out += ['', 'Checks with no lever (data_quality per book, missing_input_is_named) grade plain stated rules and stay below the 25% secondary limit together: 13 of 98.', '', '## Lessons for the master', '', '- Lever weight per check follows directly from the cost runs | no change: LEVERS.md is generated from tmp/cost/*.json.']
open('LEVERS.md','w').write('\n'.join(out)+'\n'); print('\n'.join(out))
