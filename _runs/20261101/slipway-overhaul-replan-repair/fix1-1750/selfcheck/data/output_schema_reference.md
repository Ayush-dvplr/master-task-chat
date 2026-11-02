# Output schema reference

Twenty five documents, written in this order of identifiers. Every delimited
document carries the header line named here, in this column order, and the row
order named here. Every whole quantity is an integer in the unit its stage
names. Every ratio carries exactly twelve decimal places.

## 01_identifier_canon.json
Keys: `round_key`, `round_index`, `yard`, `workbook_sheet_key`,
`jobs_in_force`, `aliases_active`, `set_aside_count`, `precincts`.
`precincts` is a list, one object per precinct in ascending precinct code,
with keys `code` and `jobs`. `aliases_active` is the count of active crosswalk
rows.

## 02_precedence_edges.tsv
Header `edge_id`, `requiring_job`, `required_job`, `precinct`, `state`,
`reason`. One row per lodgement the journal holds that concerns the round,
accepted or rejected. The state is `accepted` or `rejected`. The reason is the
rejection code for a rejected row and empty for an accepted one. For an
accepted row the edge identifier is the lowest identifier naming that pair.
Rows ascend by edge identifier, then requiring job, then required job.

## 03_reverse_index.json
An object keyed by job identifier, each value the ascending list of jobs that
name that job directly as a prerequisite. A job that nothing names is absent.

## 04_normalised_jobs.csv
Header `job_id`, `precinct`, `class`, `standing`, `base_charge_mills`,
`crew_minutes`, `berth_quarter_days`, `crane_lifts`, `deferral_weight`,
`admissible`, `admission_reason`. One row per job in force, ascending by job
identifier. `admissible` is `yes` or `no`; `admission_reason` is empty for an
admissible job.

## 05_normalised_rules.csv
Header `rule_id`, `precinct`, `kind`, `subject_a`, `subject_b`, `pool`,
`threshold`, `class`, `amount_mills`, `rebate_bp`. One row per charge rule in
force, ascending by rule identifier. `subject_a` is the first job of a pair
surcharge or the anchor job of a closure rebate. A cell a kind does not carry
is empty.

## 06_feasibility_map.csv
Header `job_id`, `precinct`, `admissible`, `blocked`, `reason`, `selectable`.
One row per job in force, ascending by job identifier. Each of `admissible`,
`blocked` and `selectable` is `yes` or `no`.

## 07_closure_map.jsonl
One record per job in force, ascending by job identifier, keys `job_id`,
`precinct`, `closure`, `closure_size`, `blocked`, `reason`. `closure` is the
ascending list of the jobs standing behind it.

## 08_demand_vectors.csv
Header `job_id`, `precinct`, `own_berth_quarter_days`, `own_crane_lifts`,
`own_crew_minutes`, `closed_berth_quarter_days`, `closed_crane_lifts`,
`closed_crew_minutes`. One row per job in force, ascending by job identifier.

## 09_conflict_groups.json
Keys `groups` and `rejected_memberships`. `groups` is a list in ascending
group identifier with keys `group_id`, `precinct`, `precedence`, `members`,
`binding`. `rejected_memberships` is a list with keys `group_id`,
`member_job`, `reason`.

## 10_charge_contributions.csv
Header `job_id`, `precinct`, `class`, `multiplier_bp`, `base_charge_mills`,
`scaled_charge_mills`, `deferral_weight`, `deferral_penalty_mills`,
`implausible`. One row per job in force, ascending by job identifier.

## 11_baseline_selection.json
Keys `precincts`, `total_mills`, `weighted_resource`, `accepted_job_count`.
`precincts` is a list in ascending precinct code with keys `precinct`,
`selected`, `closed_set`, `total_mills`, `base_mills`, `surcharge_mills`,
`rebate_mills`, `penalty_mills`, `optional_count`, `weighted_resource`,
`usage`, `available`. `selected` is the subset the search named, in the
canonical job order of the precinct; `closed_set` is that subset opened, in
ascending job identifier. `usage` and `available` are objects keyed by pool.
`accepted_job_count` is the total size of the closed sets.

## 12_baseline_trace.jsonl
One record per precinct in ascending precinct code, keys `precinct`,
`selectable_count`, `subsets_examined`, `subsets_group_rejected`,
`subsets_capacity_rejected`, `subsets_feasible`, `base_mills`,
`surcharge_mills`, `rebate_mills`, `penalty_mills`, `total_mills`.

## 13_amendment_classification.csv
Header `sequence`, `amendment_id`, `lodged_kind`, `applied_kind`,
`classification`, `reason`, `seed_count`, `seed_cells`. One row per amendment
in ascending sequence. The classification is `governed`, `inert` or
`rejected`. The reason is empty except on a rejected amendment. `seed_cells`
is the ascending seed set joined by semicolons and is empty when nothing is
seeded. A cell is named as its layer, a vertical bar, and the job, rule, group
or precinct it stands for.

## 14_invalidation_sets.jsonl
One record per amendment in ascending sequence, keys `sequence`,
`amendment_id`, `seed_cells`, `invalidated`, `revalidated`,
`invalidated_count`, `revalidated_count`. `invalidated` is the ascending list
of the cells whose digest moved. `revalidated` is the ascending list of the
cells that were visited and came back with the digest they already held.

## 15_reuse_ledger.csv
Header `sequence`, `amendment_id`, `layer`, `visited`, `recomputed`,
`revalidated`, `reused`. Seven rows per stage, the layers in the order
`norm`, `rule`, `closure`, `demand`, `charge`, `group`, `solve`. The build is
sequence 0 with an empty amendment identifier; then one stage per amendment in
ascending sequence. `visited` counts the cells of that layer the stage
reached, `recomputed` those it had to derive again because the store did not
hold the key, `revalidated` those that came back with the digest they held,
and `reused` is the cells of that layer the stage never reached at all.

## 16_work_counters.csv
Header `stage`, `sequence`, `amendment_id`, `cells_visited`,
`cells_recomputed`, `cells_revalidated`, `cells_reused`, `subsets_examined`,
`cache_hits`, `cache_misses`, `cache_evictions`. The stage is `build` or
`amendment`. One row for the build and one per amendment. The cache columns
are the movement over that stage alone, not a running total. `subsets_examined`
counts the subsets the solves derived again during that stage, so a solve read
back out of the store adds nothing to it.

## 17_cache_summary.json
Keys `retention`, `entries_in_force`, `entries_retained`, `hits`, `misses`,
`evictions`, `hit_ratio`. The ratio is hits over hits plus misses, to twelve
decimal places, and is an exact zero when nothing was looked up.

## 18_final_selection.json
The shape of `11_baseline_selection.json`, after every amendment.

## 19_rejected_register.csv
Header `scope`, `identifier`, `reason`, `detail`. The scope is `job`, `edge`,
`group_membership` or `amendment`. For a job the detail is its precinct, for
an edge the requiring job, a greater than sign and the required job, for a
group membership the member job, and for an amendment its lodged kind. Rows
ascend by scope, then identifier, then reason, then detail.

## 20_resource_usage.tsv
Header `precinct`, `pool`, `capacity`, `carried`, `available`, `usage`,
`headroom`, `weight_numerator`, `weight_denominator`, `weighted_usage`. Three
rows per precinct, the pools in ascending pool name, the precincts in
ascending code, taken over the final selection. The headroom is the available
quantity less the usage. The weighted usage carries twelve decimal places.

## 21_amendment_optima.csv
Header `sequence`, `amendment_id`, `precinct`, `total_mills`,
`weighted_resource`, `accepted_job_count`, `optimum_moved`. One row per
amendment per precinct, the amendments in ascending sequence and the precincts
in ascending code, holding the standing of that precinct after that amendment.
`optimum_moved` is `yes` when the solve of that precinct came back with a
digest other than the one it held before that amendment.

## 22_defect_register.md
A markdown table with the columns `stage`, `reason code` and `label`, one row
per reason code of the catalogue that this contract names, ascending by stage
then code, under the heading `# Defect register`, and a closing line naming
the modules in force.

## 23_verification_notes.md
The heading `# Verification notes`, a blank line, then one line for each of:
the round key, the round index, the workbook sheet key, the jobs in force, the
jobs set aside, the edges accepted, the edges rejected, the amendments
applied, the amendments classified inert, the precinct optima moved, the cells
in the model, the cells recomputed after the build, the store retention, the
store evictions, the baseline total mills and the final total mills.

## 24_run_manifest.txt
One line per document above, in this order, the file name, a space and the
digest of its bytes. A last line reads `publication` and the digest of the
lines before it.

## 25_summary.json
Keys `round_key`, `round_index`, `package`, `modules`, `control_totals`,
`final_weighted_resource`. `control_totals` carries `jobs_in_force`,
`jobs_set_aside`, `edges_accepted`, `edges_rejected`, `groups_open`,
`amendments_applied`, `baseline_total_mills`, `final_total_mills`,
`baseline_accepted_jobs`, `final_accepted_jobs`, `cells_in_model`,
`cells_recomputed_after_build`, `subsets_examined_after_build`, `cache_hits`
and `cache_evictions`.
