import json, pathlib
W = pathlib.Path('.')
def failed(p):
    d = json.load(open(p))
    return [r[0] for r in d['rows'] if (r[1] > 0) != bool(r[2])]
refs = {
 'missing_input_exit': ('missing input file: nonzero exit, stderr names it', 'contract.md:11-12'),
 'night_order_by_id': ('nights run in audit.toml date order', 'contract.md:42'),
 'dup_job_unchecked': ('E_DUP_JOB', 'contract.md:47'),
 'absent_window_unchecked': ('E_BAD_WINDOW: absent window', 'contract.md:48'),
 'window_bounds_unchecked': ('E_BAD_WINDOW: 0 <= start < end <= 1440', 'contract.md:48-49'),
 'unknown_family_unchecked': ('E_UNKNOWN_RESOURCE: family', 'contract.md:50'),
 'unknown_client_unchecked': ('E_UNKNOWN_RESOURCE: client', 'contract.md:50-51'),
 'fee_table_unchecked': ('E_BAD_FEE', 'contract.md:52-53'),
 'code_priority_swapped': ('first applicable code in stated order', 'contract.md:44-45'),
 'message_format': ('rejection message text', 'contract.md:55'),
 'rejected_resets_families': ("rejected night leaves every bay's family as it was", 'contract.md:55-56'),
 'qualification_ignored': ('job runs on a qualified bay', 'contract.md:61-62'),
 'touching_forbidden': ('half-open windows, touching jobs share no minute', 'contract.md:62-64'),
 'mandatory_optional': ('every mandatory job runs', 'contract.md:64'),
 'fee_not_charged': ('changeover pays fee of ordered pair', 'contract.md:75-76'),
 'bay_busy_in_window': ("bay's earlier job ends by crew window start", 'contract.md:78-79'),
 'window_before_zero': ('no crew window before minute 0', 'contract.md:79'),
 'bay_charge_inclusive': ('bay charge = minute_rate x (end - start)', 'contract.md:85'),
 'job_net_without_fee': ('job net = value - bay charge - fee', 'contract.md:85-86'),
 'plan_lines_by_job_id': ('plan items ordered by start then job id', 'contract.md:110-111'),
 'crew_windows_by_job_id': ('crew windows ordered by start', 'contract.md:120-121'),
 'families_after_dropped': ('families_after at night end', 'contract.md:121-122'),
 'crew_flag_dropped': ('crew_load_high flag', 'contract.md:123-124'),
 'margin_flag_dropped': ('low_margin flag', 'contract.md:124'),
 'flags_unsorted': ('flags alphabetically sorted', 'contract.md:122-123'),
 'region_not_by_site': ("region of the client's site", 'contract.md:102'),
 'segment_not_by_client': ('segment of the client', 'contract.md:102'),
 'rollup_skips_empty_nights': ('rollups list every accepted night', 'contract.md:137-138'),
 'rollup_totals_partial': ('rollup totals', 'contract.md:139-140'),
 'summary_totals_partial': ('summary totals', 'contract.md:113-114'),
 'rejected_night_omitted': ('rejected night: empty plan, zero figures', 'contract.md:112-113'),
 'data_dir_ignored': ('program reads DATA_DIR, writes OUT_DIR', 'instruction.md:3'),
}
lever = [
 ('LV-CW-1 maximum net plan', 'contract.md:89-91', 'greedy (mutants/greedy.py)', 'cost/greedy.json'),
 ('LV-CW-1 maximum net plan', 'contract.md:89-91', 'greedy_ls', 'cost/greedy_ls.json'),
 ('coupling: every figure from the maximum-net-value plan', 'contract.md:97', 'greedy_ls', 'cost/greedy_ls.json'),
 ('LV-CW-2 initial_family until first job', 'contract.md:68', 'no_initial', 'cost/no_initial.json'),
 ('LV-CW-2 previous family = latest-starting earlier job (across gaps)', 'contract.md:70-71', 'touching_only', 'cost/touching_only.json'),
 ('LV-CW-2 family held at night start (carry across nights)', 'contract.md:71-73', 'reset_nightly', 'cost/reset_nightly.json'),
 ('LV-CW-3 single crew, windows never share a minute', 'contract.md:79-80', 'no_crew', 'cost/no_crew.json'),
 ('LV-CW-3 crew window [start - crew_minutes, start) ends at job start', 'contract.md:77-79', 'naive_collapse', 'cost/naive_collapse.json'),
 ('LV-CW-3 qualification and crew per bay (shared state)', 'contract.md:61-62,79-80', 'flow_relax', 'cost/flow_relax.json'),
 ('LV-CW-3 plans per night across all bays', 'contract.md:61-64,89-91', 'lane_by_lane', 'cost/lane_by_lane.json'),
]
out = ['# RULE_COVERAGE', '', 'Each mutant is the oracle `solution/solve.py` with one rule dropped (WORK/rule_mut/<id>.py, lever rows WORK/mutants/<name>.py), run through every check of `tests/test_output.py` by WORK/run_tests.py. Last cell = number of checks the mutant fails.', '',
       '| rule | file:line | mutant | tests failed |', '|---|---|---|---|']
names = {}
for rid, (rule, ref) in refs.items():
    f = failed(W/'tmp/rule'/(rid+'.json')); names[rid] = f
    out.append(f'| {rule} | {ref} | {rid} | {len(f)} |')
out.append('| output paths region_North.json and the rest (case) | instruction.md:5-11 | output_paths_lowercase | 23 |')
for rule, ref, m, p in lever:
    f = failed(W/'tmp'/p); names[m] = f
    out.append(f'| {rule} | {ref} | {m} | {len(f)} |')
out += ['', 'Notes', '',
 '- output_paths_lowercase passes every check on macOS (case-insensitive APFS); it was run in Linux Docker (python:3.12-slim, uid 1000) where it scores 17/98 and fails 23 checks (shipped regions, every hidden summary, regions and relocated rerun). That Linux figure is the one recorded.',
 '- Tie order (contract.md:91-95) has no row: every shipped and hidden night has exactly one maximum-net plan (counted at build time, WORK/datagen.py and WORK/hidden_build.py assert count == 1), so a tie mutant changes no output. The rule is kept as stated by IDEA G-3. Open point for the master: G-3 and G11 conflict on this rule.',
 '- Stated limit (contract.md:19-20, 2 s per night) is covered by raw_exact and raw_tuned in COST_TABLE.md.',
 '', 'Failed checks per mutant', '']
for k, f in names.items():
    out.append(f'- {k}: ' + ', '.join(f))
out += ['', '## Lessons for the master', '',
 '- Case of output names only shows on a case-sensitive file system | template_change: no change: run rule mutants inside the Linux image, not on the Mac.',
 '- A unique-optimum design leaves the stated tie rule untestable | no change: master decides G-3 versus G11.']
open('RULE_COVERAGE.md','w').write('\n'.join(out)+'\n')
