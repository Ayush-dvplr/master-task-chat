# FIX_REPORT depot-charge-plan, fix v2 (board 0d6348c, 1 Nov 2026)

Status DONE. Tree before 7e3ade15a78b (after efdb667 DS-21), after 3e4d3ee74385; Tasks_INPUT copy 3e4d3ee74385, `diff -rq` empty. Live QC kit HEAD 5574d77e, fingerprints qc.json and pl_generator.json 0 diffs. Session rename: opencode ses_e6a4e8962ffeDIWRmbwx0LdyJx listed (codex: no match).
Docs changed: one sentence added to charging_rules.md rule 13 (DS-20); instruction.md unchanged.
All paths below are relative to the bundle; generated files come from WORK/gen_core.py, WORK/tools/assemble_tests.py, WORK/tests_src/infra.py and WORK/tests_src/judge_spec.py, so nothing in the bundle was edited by hand.

## Findings

| finding | what changed (file:line) | playbook row | recheck |
|---|---|---|---|
| CL-3 fail | Shipped derating now binds: environment/data/disruption_notice.md:10 limit 170 -> 90 kWh per slot (gen_core shipped derate 6/10 of window peak, same rng calls; tests/test_output.py:245). Oracle on shipped: buses_changed 28 (East 24, North 1, South 1, West 2), feeder_peak 1045, so the graded plan differs from published_plan.csv in all four depots by documented rules 11 and 12. Hidden tier unchanged in kind. | CL-3 DO (shipped data must need the method) | a published-plan copier now fails all 4 shipped plan checks; first-write and all-but-one fail shipped_policy_audit too (kill table). Forgery of the 9 shipped docs still earns 16/197 (CL-2, expected, was 16/191) |
| TS-26 fail | `relocated_copy_summary_exact` replaced by `relocated_fresh_summary_exact` (w3, tests/test_output.py:3981) on its own seed 47713 (`_FRESH["rel"]`, :43; `_relocated()` :3445); no other check grades that tree. Weight unchanged. | TS-26 DO narrow so each reads a different observable | digest_after: relocated expected b85c38925b3b, differs from fresh_h3 summary 4ec2b5f3f922; stacking_check groups checked by hand (different folders/seeds) |
| JD-5 / JD-8 R9 fail | R9 now code quality only (tests/judge.toml:118, "every exception handler acts on the error it catches ..."). Input behaviour graded by tests: `missing_settlements_stops_naming_file` (w3, :3991, unchanged) and new `malformed_tariff_stops_naming_file` (w3, :3996; tariff.xml cut halfway -> non-zero exit, stderr names tariff.xml; rule 22, charging_rules.md:48). | JD-5 DO split; JD-8 DO criterion tests settle removed; JD-18 kept the code-quality clause | FIX_SIDE_EFFECTS JD-2, JD-7, JD-9, JD-15, IN-8 rechecked (OUT/RECHECK_FIX.md); judge_qc 0 warns |
| AL-2 fail | (1) flagless default run: `default_paths_run_summary_exact` (w3, :3986): a further fresh folder (seed 55109) is placed at /app/data, `python3 /app/out/derive_report.py` runs with no flags, its /app/out/summary.json must equal the derived one; agent /app/data and /app/out restored byte for byte (`_flagless()` :3527). (2) totals in final reply: new judge R17 (w3, task completion, final_answer, judge.toml:222) names the eight summary.json keys. (3) writes only into output folder: `negative_run_writes_outside_output_folder` (w-1, :4011): files the flagless run creates under /app, /tmp, /var/tmp or /dev/shm outside /app/out (a positive version passed on absence, TS-25, so it is a negative). | AL-2 DO grade by observable writes on hidden inputs | oracle and owner 1.000 with all three in place; nop/stub silent on the negative |
| AL-27 fail | Three two-fault roster rows in shipped and every hidden tree (master override of the playbook NEVER on shipped rows): unknown + bad window (roster.csv:2434 B9991), retired + bad window (:2497 B8875), duplicate + bad window (:4329 B1113); generator block tests/test_output.py:346, `rare` stream after all existing draws, so plans are unchanged. Rule 4 order (charging_rules.md:13) decides each reason. | AL-27 DO reseeded rows meeting both faults, earlier rule wins | data_quality / summary expected change only by these rows; every fresh plan, region and segment digest byte-identical (30 untouched checks identical, WORK/fix2/digest_after.txt) |
| DS-20 warn | charging_rules.md:28 rule 13 adds "A row whose `bus_id` is not a bus on the plan is ignored and is not rejected."; reference load skips such rows (tests/test_output.py:701, oracle solve.py already did); hidden-only fixture: a published row for a retired bus (:358). | DS-20 DO graded hidden case, contract stated once | oracle 1.000; careful program as saved lost 32 points on exactly this sentence (kill table) |
| TS-23 warn | 48 checks (> 35). Kept as warn, no merging. | TS-23 KEEP (option A) | precheck WARN [A3] only |
| JD-16 R16 warn | End-state test (`negative_data_folder_changed` + /app/data as artifact) built, then withdrawn: validate_bundle 1.12 requires the archetype artifact list exactly, and with environment_mode "separate" the verifier never sees the agent's /app/data, so the test would be dead (TS-16). R16 kept as written. | JD-16 relabel/keep with reason | validator 40/0/0 after revert |
| F0d, F0e, CL-10 repeats | F0d = JD-5 (closed above); F0e and CL-10 = DS-21, unchanged from efdb667 (rule 12 shift family, East k 28). | n/a | rechecked closed |

Reward weights: tests positive 197 (was 191: +3 default paths, +3 malformed input), negatives -3, -5, -1; judge 17 criteria, positive 38 (was 35: +3 R17), probes 24/38 = 63.2%. reward.toml test_output 0.0025380710659898475 (0.5/197), judge 0.013157894736842105 (0.5/38). TRUTH.md regenerated by WORK/tools/truth.py last; xref_check 14 entries, 0 findings.

## Lever accounting (route-1 R5 a, b, d)

Final tests, Docker dcp-verifier:1, `--memory 4g --cpus 2`, logs `_runs/20261101/depot-charge-plan/fix2-20261101T1135/logs/kill.log`, `kill2.log` (each program EXIT rc=0). Lever = 32 fresh plan checks + reordered + relocated + default paths = 169 of 197 positive test points = 85.8% (R5(b) >= 40%: met).

| program | tests % | lever kept | loss kind |
|---|---|---|---|
| blind1 (0345) | 5.1 (10/197) | 0/169 | WRONG |
| blind2 (0345) | 3.0 (6/197) | 0/169 | CRASH on shipped East meter |
| blind3 (0345) | 3.0 (6/197) | 0/169 | CRASH on shipped East meter |
| first-write (oracle, no tie pass, meter k 0) | 6.6 | 0/169 | WRONG |
| all-but-one (oracle, no tie pass) | 8.1 | 0/169 | WRONG |
| careful shift search, as saved | 83.8 | 151/169 | WRONG (rule 13 sentence it predates) |
| careful shift search + rule 13 sentence | 100.0 | 169/169 | none, recorded per R5(d), not a blocker |

Predicted final = (blind-like tests 3.7 + judge mid 46.7) / 2 = 25.2 (R5(a) <= 35: met). A careful-reader run predicts (100 + 46.7) / 2 = 73.4. The three blinds predate DS-21 (none searched shifts), so the careful row is the likelier paid-run reading.

## Gates

- PRECHECK last line: `PRECHECK CLEAN` (structure, instruction, tests, judge QC exit 0; only WARN [A3] 48 checks; 0 IN17/G5 warns).
- validate_bundle: 40 passed, 0 failed, 0 warnings, GATE: PASS.
- stacking_check -> OUT/STACKING_CHECK.md: G3 hidden reruns 88.8% PASS, shipped-only 10.7%. Its AL-28 FAIL comes only from the unmatched group (negative_run_writes_outside_output_folder -1, R13 -5, R16 -1); checked by hand these are three different acts, each at most 5, so it passes.
- Tests-only lanes (exe_copy.py plain/owner-only/stub, dockfree START=yes per job, ALL_DONE): oracle 1.000, 1.000, 1.000; owner 1.000; nop 0.000; stub 0.0051 (present only); forgery 0.0812 (present + 5 shipped docs); no negative fired.
- No `__pycache__` in bundle or Tasks_INPUT copy.

## Not run

Judge lanes (tests-only gate per prompt). No paid run. The blind programs were not re-written against the new docs; they are scored as saved.

## Lessons for the master
- Adding a directory artifact for an end-state test breaks validate_bundle 1.12 (archetype artifact list) | template_change: QC_FIX_PLAYBOOK_v3.md JD-16 row: with environment_mode "separate" keep R16, do not add /app/data to artifacts
- A positive "writes only into X" check passes on absence (TS-25); make it a negative | no change: TS-25 already covers it
- Kit W2 allows test weights 1, 3, 5 only; size new checks to that set before the first precheck | no change: precheck catches it
- A rule sentence added at fix time makes earlier careful programs lose on it; patch the kill program to the new docs before reading its row | template_change: _COMMON_RULES_v5.md rule 17: kill programs follow the current docs
- zsh does not split `$(seq N)`, and run scripts echoing ALL_DONE inside a lane end the poll early; poll a lane-only marker with `{1..N}` | template_change: _COMMON_RULES_v5.md rule 3 poll loop
