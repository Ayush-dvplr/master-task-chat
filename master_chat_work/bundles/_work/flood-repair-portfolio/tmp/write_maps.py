import json, glob, os, sys
sys.path.insert(0, '.')
import rule_mutants, mutants
def load(d, n):
    r = json.load(open('%s/%s.json' % (d, n)))
    failed = [x for x, w, ok, _ in r['rows'] if (w > 0 and not ok) or (w < 0 and ok)]
    pos = sum(w for _, w, _, _ in r['rows'] if w > 0)
    lost = sum(w for x, w, ok, _ in r['rows'] if w > 0 and not ok)
    return r, failed, pos, lost
lever_of = {}
for name, lev in [(k, 'LV-FP-1') for k in mutants.OPTIMISERS] + [(r[0], r[1]) for r in mutants.RULES]:
    lever_of[name] = lev
for r in rule_mutants.RULES:
    lv = {'19':'LV-FP-4','21':'LV-FP-4','37':'LV-FP-4','38':'LV-FP-4','39':'LV-FP-4','40':'LV-FP-4','42':'LV-FP-4','58':'LV-FP-2','64':'coupling'}.get(r[2], 'stated')
    lever_of[r[0]] = lv
res = {}
for n in lever_of:
    d = 'mut_results' if os.path.exists('mut_results/%s.json' % n) and n in dict(mutants.RULES and [(x[0],1) for x in mutants.RULES]) | dict.fromkeys(mutants.OPTIMISERS) else 'rule_results'
    res[n] = load(d, n)
rows0 = json.load(open('rule_results/third_party_import.json'))['rows']
checks = [(x, w) for x, w, _, _ in rows0]
# LEVERS.md
L = ['# LEVERS flood-repair-portfolio', '',
     'One row per check of tests/test_output.py. A lever id is listed when at least one wrong program for that lever (WORK/mutants/*.py lever rows, WORK/rule_mut/*.py stated-rule rows) fails the check. "stated" = a stated output-format or fault-reporting rule outside the four levers.', '',
     '| check | weight | levers |', '|---|---|---|']
tot = {}
for c, w in checks:
    levs = sorted({lever_of[n] for n, (_, f, _, _) in res.items() if c in f})
    if w < 0: levs = ['G4 cheat act']
    L.append('| %s | %d | %s |' % (c, w, ', '.join(levs) or 'none'))
    for l in levs:
        if w > 0: tot[l] = tot.get(l, 0) + w
L += ['', '| lever | positive weight of checks it can fail | share of 108 |', '|---|---|---|']
for l in sorted(tot): L.append('| %s | %d | %.0f%% |' % (l, tot[l], 100*tot[l]/108))
L += ['', 'Negative checks: negative_program_reads_verifier_files -5, negative_hardcoded_sample_answers -3 (two distinct acts, AL-28).']
open('LEVERS.md', 'w').write('\n'.join(L) + '\n')
# RULE_COVERAGE.md
lines = ['# RULE_COVERAGE flood-repair-portfolio', '',
 'Each mutant is the oracle solution/solve.py with one rule dropped or misread (WORK/rule_mut/<id>.py; lever rows WORK/mutants/<name>.py), run through every check of tests/test_output.py with WORK/run_tests.py. Last cell = number of checks the mutant fails (score in brackets). Every row is at least 1.', '',
 '| rule | file:line | mutant | tests failed |', '|---|---|---|---|']
rule_line = {r[0]: (r[1], r[2]) for r in rule_mutants.RULES}
mut_rule = {'greedy_benefit': ('greatest total benefit', '62'), 'greedy_ratio': ('greatest total benefit', '62'), 'greedy_swaps': ('greatest total benefit', '62'), 'timed_bnb': ('greatest total benefit', '62'), 'timed_ils': ('greatest total benefit', '62'),
 'no_tiebreak': ('tie-break: smaller sorted id list', '62'), 'tiebreak_largest': ('tie-break: smaller sorted id list', '62'),
 'no_crew': ('exclusive crew joins its proposals', '56'), 'shared_crews_too': ('shared crew joins nothing', '27'), 'no_permit': ('held/applied permit joins its proposals', '57'), 'withdrawn_counts': ('withdrawn permit row counts for nothing', '57'), 'no_exclusion': ('exclusion entry joins the pair', '58'), 'site_names_ignored': ('a site name stands for every proposal of the round at that site', '29'),
 'no_override': ('risk_override replaces the site class', '23'), 'no_premium': ('site premium added', '48'), 'uplift_flat': ('households x (rate + uplift)', '48'), 'no_uplift': ('risk uplift added to the rate', '50'),
 'fixed_file_order': ('round files checked in manifest order', '35'), 'invalid_before_duplicate': ('checks in listed order', '37'), 'first_occurrence_duplicate': ('DUPLICATE_PROPOSAL at the second occurrence', '37'), 'row_within_round': ('row numbers of the whole file', '21'), 'value_before_files': ('NONPOSITIVE_BENEFIT only after file checks', '42')}
allrows = [(mut_rule[n][0], mut_rule[n][1], 'mutants/' + n) for n in mut_rule] + [(rule_line[n][0], rule_line[n][1], 'rule_mut/' + n) for n in rule_line]
allrows.sort(key=lambda r: int(r[1]))
unc = 0
for rule, ln, m in allrows:
    n = m.split('/')[1]; r, f, pos, lost = res[n]
    unc += len(f) == 0
    lines.append('| %s | environment/data/contract.md:%s | %s | %d (%.3f) |' % (rule, ln, m, len(f), r['score']))
lines += ['', 'Rules uncovered: %d.' % unc]
open('RULE_COVERAGE.md', 'w').write('\n'.join(lines) + '\n')
json.dump({n: {'lever': lever_of[n], 'score': res[n][0]['score'], 'failed': res[n][1], 'lost': res[n][3]} for n in res}, open('tmp/mut_summary.json', 'w'), indent=1)
print('uncovered', unc, tot)
