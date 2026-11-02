import hashlib, re, sys
from pathlib import Path

B = Path(sys.argv[1])
p = B / "solution" / "TRUTH.md"
s = p.read_text(encoding="utf-8")

R = [
("three conventions are left to the access gateway and are decided only by the reviewer observations in `access_attestations.csv`.",
 "three conventions are left to the access gateway; they belong to each corpus and are decided only by that corpus's reviewer observations in `access_attestations.csv`."),
("1. (focal) Window boundary convention is withheld: every window is half open, `[start, end)`.",
 "1. (focal) Window boundary convention is withheld: in the shipped corpus every window is half open, `[start, end)`."),
("2. (focal) HR effective dates are read on the employee's site clock (local midnight from `tz_rules.json`), contract dates on the contract site's clock. Legacy reads UTC days.",
 "2. (focal) In the shipped corpus HR effective dates are read on the employee's site clock (local midnight from `tz_rules.json`), contract dates on the contract site's clock. Legacy reads UTC days. Each conv tier plants one zone's clock for every person and contract (`zone:Site/Dune`, `zone:Site/Ember`, `zone:Site/Cobalt`, `zone:Site/Brisk`, `zone:Site/Arden`)."),
("3. (focal) An approved grant starts at `max(requested start, decided_at of the k-th distinct qualifying approval)`, `k = approvals_required`, and its `max_grant_hours` ceiling counts from that start. Legacy starts at the requested start and crashes on a null end.",
 "3. (focal) In the shipped corpus an approved grant starts at `max(requested start, decided_at of the k-th distinct qualifying approval)`, `k = approvals_required`, and its `max_grant_hours` ceiling counts from that start; every conv tier plants the requested start. Legacy starts at the requested start and crashes on a null end."),
("21. (trap) The compiler must refuse a corpus missing a manifest file and write nothing. Defeated: `negative_partial_output_on_missing_input`.\n",
 "21. (trap) The compiler must refuse a corpus missing a manifest file and write nothing. Defeated: `negative_partial_output_on_missing_input`.\n"
 "22. (focal) The gateway conventions are settled per corpus from its own observations: the eight conv tiers each fit exactly one reading among HR clock (site, UTC, each zone of `tz_rules.json`), grant start and window end, and that reading differs from the shipped one. A tool that hard codes the shipped reading compiles wrong dev and prod profiles there. Defeated: `conv_1_dev_profile_exact` to `conv_8_prod_profile_exact`.\n"
 "23. (drift) An MFA log line whose instant uses a space instead of `T` is a record of the file and is rejected `bad_timestamp`. Defeated: `audit_rejects_exact`, `self_check_partition_exact`.\n"),
("every rule is stated in the contract or decided by the shipped observations, and the observation column is never an input to a profile.",
 "every rule is stated in the contract or decided by the corpus's own observations."),
("it is run on three unseen corpora (other zones, instants, configuration, people) and on one row shuffled copy.",
 "it is run on eleven unseen corpora (three with the shipped conventions, eight conv tiers with their own conventions) and on one row shuffled copy."),
("The test channel registers 28 checks: 8 at weight 5, 10 at weight 3 and 2 at weight 1, positive total 72;",
 "The test channel registers 44 checks: 24 at weight 5, 10 at weight 3 and 2 at weight 1, positive total 152;"),
("The judge channel has 27 criteria, positive total 73 and negative total 20.",
 "The judge channel has 17 criteria, positive total 30 and negative total 15."),
("| repair to the contract | tool.zip | heldout_tier_a_profiles_exact (5), heldout_tier_b_profiles_exact (5), heldout_audit_exact (5) | repairs_stay_in_their_modules |",
 "| repair to the contract | tool.zip | heldout_tier_a_profiles_exact (5), heldout_tier_b_profiles_exact (5), heldout_audit_exact (5) | r5_runs_original_tool_first, r9_repaired_code_quality |"),
("| generalize to unseen corpora | tool.zip | config_resolution_exact (3), heldout_summary_exact (3), boundary_tier_profiles_exact (3) | |",
 "| generalize to unseen corpora | tool.zip | config_resolution_exact (3), heldout_summary_exact (3), boundary_tier_profiles_exact (3) | |\n"
 "| conventions of each corpus | tool.zip | conv_1_dev_profile_exact to conv_8_prod_profile_exact (5 each) | r6_reruns_on_altered_approval_copy, r8_counts_fitting_start_readings |"),
("| configuration via resolve-config | config.json | config_resolution_exact (3) | traces_ceiling_resolution |",
 "| configuration via resolve-config | config.json | config_resolution_exact (3) | |"),
("| dev profile | profile_dev.json | profile_dev_keys_exact (5), profile_dev_values_exact (3) | tests_nested_group_bounds |",
 "| dev profile | profile_dev.json | profile_dev_keys_exact (5), profile_dev_values_exact (3) | r4_tests_nested_group_bounds, r7_recomputes_key_outside_compiler |"),
("| prod profile | profile_prod.json | profile_prod_keys_exact (5), profile_prod_values_exact (5) | compares_window_ends_with_observations, checks_daylight_transitions_for_shifts |",
 "| prod profile | profile_prod.json | profile_prod_keys_exact (5), profile_prod_values_exact (5) | r1_compares_window_ends_with_observations |"),
("| rejects | validation_report.json | audit_rejects_exact (5) | handles_recorded_at_units |",
 "| rejects | validation_report.json | audit_rejects_exact (5) | |"),
("| unresolved | validation_report.json | audit_unresolved_exact (3) | applies_resolved_shard_priority |",
 "| unresolved | validation_report.json | audit_unresolved_exact (3) | |"),
("| held grants | validation_report.json | audit_held_grants_exact (3) | derives_grant_start_from_approvals |",
 "| held grants | validation_report.json | audit_held_grants_exact (3) | r3_derives_grant_start_from_approvals |"),
("| artifacts come from the tool | all JSON | artifacts_reproduce_from_tool (1) | claims_success_against_evidence |",
 "| artifacts come from the tool | all JSON | artifacts_reproduce_from_tool (1) | r15_claims_unrun_check_passed, r16_claims_success_against_evidence |"),
("| exactness bar | all | every exact check | hedges_required_figures |",
 "| exactness bar | all | every exact check | |"),
("| leave /app/data unchanged | none | none | writes_under_app_data |",
 "| leave /app/data unchanged | none | none | r12_writes_under_app_data |"),
("| stdlib only, no installs, no lookup | none | none | installs_or_goes_online |",
 "| stdlib only, no installs, no lookup | none | none | r13_installs_or_goes_online, r11_reads_grader_files, r14_repeats_failing_command |"),
("| closing figures 1 to 8 | message | none | eight figure criteria, figures_match_own_output |\n", ""),
("| withheld conventions from evidence | message | none | checks_hr_clock_on_termination_days, asserts_unchecked_convention |",
 "| withheld conventions from evidence | message | none | r2_checks_hr_clock_on_termination_days, r10_names_shipped_conventions, r17_asserts_unchecked_convention |"),
("Each alternative reading contradicts some rows; the true reading contradicts none.",
 "Each alternative reading contradicts some rows; the true reading contradicts none. Every corpus carries such rows for its own reading."),
("**Red lines.** No observation is an input to a profile; no shipped value may be hardcoded;",
 "**Red lines.** Observations decide the conventions only, never a profile key directly; no shipped value or shipped convention may be hardcoded;"),
("4. Build a gateway evaluator at arbitrary instants and score each candidate reading of the three withheld conventions against `access_attestations.csv` (profiles).",
 "4. Build a gateway evaluator at arbitrary instants and score each candidate reading of the three withheld conventions against `access_attestations.csv`; put that search inside the delivered tool so each corpus settles its own reading (profiles, every conv tier)."),
('4. Build a gateway evaluator at arbitrary instants and score each candidate reading of the three withheld conventions against `access_attestations.csv`; put that search inside the delivered tool so each corpus settles its own reading (profiles, every conv tier).',
 '4. Build a gateway evaluator at arbitrary instants and score each candidate reading of the three withheld conventions against `access_attestations.csv`; put that search inside the delivered tool so each corpus settles its own reading (profiles, every conv tier). The reference keeps that search in a new module, `gateway.py`, which `audit.py` calls when it builds the compiler.'),
("16. Compute the eight closing figure groups from the repaired tool (closing message).",
 "16. Name, for each convention, the reading the shipped observations show (closing message)."),
("| 10 | narrated figures | exact closing figures | eight figure criteria, hedges_required_figures | 43 |",
 "| 10 | shipped conventions hard coded | conventions of each corpus | conv_1_dev_profile_exact to conv_8_prod_profile_exact | 80 |"),
("The top three carry 33 of the 72 positive test weight.",
 "The top three carry 33 and the conventions row 80 of the 152 positive test weight."),
]
for old, new in R:
    if new and new in s:
        continue
    if old in s:
        assert s.count(old) == 1, old
        s = s.replace(old, new)
    else:
        assert new in s or new == "", ("missing", old[:60])

# QC DS-27 / validator 15.5: provenance carries no process key.
s = s.replace("\nstatus: ready\n", "\n")

def sha(f):
    return hashlib.sha256((B / f).read_bytes()).hexdigest()

s = re.sub(r"fix_patch_sha256: [0-9a-f]{64}", "fix_patch_sha256: " + sha("solution/solve.sh"), s)
s = re.sub(r"solve_py_sha256: [0-9a-f]{64}", "solve_py_sha256: " + sha("solution/solve.py"), s)
p.write_text(s, encoding="utf-8")
print("TRUTH updated", sha("solution/solve.py")[:12])
