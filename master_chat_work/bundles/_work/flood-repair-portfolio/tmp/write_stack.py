import re, pathlib
W = pathlib.Path('.')
OUT = pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261025_flood-repair-portfolio/build/STACKING_CHECK.md')
rows = []
for line in (W/'LEVERS.md').read_text().splitlines():
    m = re.match(r'\| (\w+) \| (-?\d+) \| (.+) \|$', line)
    if line.startswith('| lever |'): break
    if m and m.group(1) not in ('check',):
        rows.append((m.group(1), int(m.group(2)), m.group(3)))
def obs(name):
    if name == 'artifacts_present': return ('the ten /app/out paths exist after the shipped run', 'existence of files')
    if name.startswith('shipped_'):
        d = {'summary': 'summary.json', 'policy_audit': 'policy_audit.json', 'data_quality': 'data_quality.json',
             'regions': 'the four region_*.json', 'segments': 'the two segment_*.json'}[name[8:].replace('_matches','').replace('_match','')]
        return (f'{d} written by the agent on the shipped book', 'whole-document equality with the reference, first differing path')
    m = re.match(r'(h\d)_book_(\w+)', name)
    if m:
        b, k = m.group(1).upper(), m.group(2)
        if k == 'feasible': return (f'selected lists of every planned round of fresh book {b}', 'conflict-free and maximal under the stated conflict rule')
        if k == 'optimal': return (f'selected lists of every planned round of fresh book {b}', 'equal to the unique tie-broken optimum per round')
        d = {'summary': 'summary.json', 'policy_audit': 'policy_audit.json', 'data_quality': 'data_quality.json',
             'regions': 'the four region_*.json', 'segments': 'the two segment_*.json'}[k]
        return (f'{d} of fresh book {b}', 'whole-document equality, first differing path')
    return {
        'scaled_shuffled_summary_matches': ('summary.json of book M with segment rates scaled by 1.37 and rows shuffled', 'whole-document equality'),
        'rotated_summary_matches': ('summary.json of book M with rows rotated by a third', 'whole-document equality'),
        'relocated_copy_matches': ('all ten documents of book M copied under a folder path with spaces', 'whole-document equality of every document'),
        'missing_input_is_named': ('exit code, stderr and out folder with permits.csv / exclusions.json deleted', 'exit 1, ERROR MISSING_FILE first missing file, no documents'),
        'reruns_identical': ('bytes of two runs of book H1 from different folders', 'byte equality between runs'),
        'negative_program_reads_verifier_files': ('source text of /app/out/*.py', 'refers to /tests paths'),
        'negative_hardcoded_sample_answers': ('source text of /app/out/*.py', 'holds >=3 shipped selected ids or the shipped total'),
    }[name]
L = ['# STACKING_CHECK flood-repair-portfolio', '',
     'Started from `tools/stacking_check.py` (34 checks, positive 108, negatives -8; judge 11 criteria, positive 30, batched) and corrected by reading tests/test_output.py.', '',
     '## (a) One row per test', '',
     '| test | w | observable | decisive logic | levers whose misread fails it |', '|---|---|---|---|---|']
for n, w, lv in rows:
    o, l = obs(n); L.append(f'| {n} | {w} | {o} | {l} | {lv} |')
L += ['',
 'TS-26 by hand: the tool grouped 7 sets by shared helper only. Inside each group the observable differs: h1/h2/h3 checks read documents of three different fresh books (different seeds, different large rounds), the M mutation checks read a different book under a different mutation, regions vs segments are different documents (region_*.json vs segment_*.json) with a different partition, and artifacts_present / relocated / missing / reruns read existence, a relocated copy, an exit code and byte equality respectively. No two rows share both observable and logic (TS-26 PASS, district-heat v3:185 whole-doc per view per extract). Each row tests one property, a whole document or one feasibility/optimality fact (TS-13 PASS, whole-document per view is one property).', '',
 'Judge hints by hand: J1 flagged R6 and R8 for numbers; R6 quotes the stated size bound for enumeration (16 proposals) and R8 the contract time limit (20 seconds), neither is a graded figure. J2 regex found none because our conduct criteria are worded "The agent independently recomputes ... outside its program"; R1-R8 are the J2 conduct criteria, each performed by solve.sh printing `check R<n> ok`.', '',
 '## (b) Penalty groups by act', '',
 '| act | tests | judge | sum abs w | verdict |', '|---|---|---|---|---|',
 '| naming or reading grader files | negative_program_reads_verifier_files -5 | - | 5 | PASS |',
 '| hardcoding the shipped answers | negative_hardcoded_sample_answers -3 | - | 3 | PASS |',
 '| claiming an unrun check passed | - | R11 -5 | 5 | PASS |', '',
 'No negative grades a lever: both test negatives inspect source text for cheating acts only (G4).', '',
 '## (c) Weight shares (positive test weight 108)', '',
 '- Tool: whole-document 65 (60.2%), isolated 24 (22.2%), shipped-only 19 (17.6%); G3 hidden or mutated reruns 60.2% >= 30% PASS.',
 '- By hand: checks on fresh books H1-H3 = 75, mutation runs on book M = 14 (scaled 5, rotated 3, relocated 3, missing file 3), rerun on H1 = 3, so hidden or mutated = 92/108 (85%); shipped book only = 16/108 (15%). The tool counts missing_input_is_named, reruns_identical and relocated_copy_matches as shipped-only by wording.', '',
 '## (d) Cost table (G10, WORK/COST_TABLE.md)', '',
 '| lever | wrong program | tests lost share | all-but-one overall | gate |', '|---|---|---|---|---|',
 '| LV-FP-1 | greedy_benefit (also greedy_swaps, timed_bnb, timed_ils, no_tiebreak) | 74-77% | 0.580 | PASS (>=25%, <0.70) |',
 '| LV-FP-2 | no_crew (also no_permit, no_exclusion, withdrawn_counts, site_names_ignored) | 94-97% | 0.482 | PASS |',
 '| LV-FP-3 | uplift_flat (also no_override, no_premium, no_uplift) | 88-94% | 0.510 | PASS |',
 '| LV-FP-4 (secondary, planned 11%) | fixed_file_order (pure order mutants lose 3-15) | 3-14% | 0.936 | secondary exemption (<=25% weight by design) |', '',
 'Overall = 0.5 x tests + 0.5 x judge with the judge share assumed 0.90.', '',
 '## (e) Rule coverage (G11, WORK/RULE_COVERAGE.md)', '',
 '- 47 rule rows (contract.md lines 5 to 78), every row fails >= 1 test; rules uncovered: 0.', '',
 '## (f) EVIDENCE_MAP and UNIQUENESS', '',
 '- Every lever rule has a contract sentence (W2); EVIDENCE_MAP.md rows cite the sentence plus a shipped fact (crews.tsv:3 shared crew, permits.csv:3 withdrawn row, exclusions.json:3 site name, proposals.csv:9 override, proposals.csv:2092/2093 zero and negative benefit, audit_queries.txt:98 blank line). No rule relies on silence; no L11 rule, so UNIQUENESS.md records optimum counts only (every large round count 1; planted ties only in small rounds).', '',
 'VERDICT: STACKING PASS']
OUT.write_text('\n'.join(L) + '\n'); print(len(L))
