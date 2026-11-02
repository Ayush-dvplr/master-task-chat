# Output artifact contract

This file fixes the exact shape of every report so a solver can produce byte-exact
output. Every JSON artifact is serialized with sorted keys, compact separators
(comma and colon, no spaces), and a single trailing newline. Integers are bare
integers. The analyte keys are glucose, calcium, lactate and creatinine, the matrix
keys are serum and whole_blood, and the tier keys are routine and stat. The batch
keys are whatever batches the run admits, sorted as strings.

summary.json is an object with exactly these keys: batch_totals, an object mapping
each batch to its committed integer total; analyte_allocations, an object mapping
each batch to an object mapping each analyte that seated at least one reading in that
batch to its committed integer, a zero included; 
convergence_rounds, an object mapping each batch to its integer round count where a
cycling batch is negative one; and unsettled_batches, the sorted list of batches
whose round count is negative one.

policy_audit.json is an object with exactly these keys: tier_totals, an object
mapping each tier to its integer total, listing only the tiers that at least one
analyte of analyte_totals belongs to, so a tier holding no such analyte is left out
rather than written as zero; carryover_ledger, a list of objects each
with keys analyte, clawed_units and batch, sorted by batch then analyte; 
excluded_reading_ids, the sorted list of the reading ids the qc-fail exclusion
removed; excluded_count, its
integer length; effective_lot, the integer effective lot; and ordered_reading_ids,
the reading ids in processing order, which are the readings that survived that
exclusion.

data_quality.json is an object with exactly these keys: objective_value, the integer
weighted objective; tier_totals, the same tier totals object; committed_grand_total,
the integer sum of all analyte totals; carryover_total_units, the integer sum of
clawed units; core_files, the list summary.json, policy_audit.json and
panel_analyte_glucose.json in that order; and core_sha256, the digest defined below.

Each of panel_analyte_glucose.json, panel_analyte_calcium.json,
panel_analyte_lactate.json and panel_analyte_creatinine.json is an object with keys
analyte, the analyte name; matrix, its matrix class; tier, its decision tier; 
committed_total, the integer analyte total; and per_batch, an object mapping each
batch whose analyte_allocations entry lists that analyte to its integer, a zero included.

matrix_rollup.json is an object with keys axis set to the string matrix; class_totals,
the matrix totals object; and analyte_membership, an object mapping each analyte to
its matrix. tier_rollup.json has keys axis set to the string tier; class_totals, the
tier totals object; weighted_objective, the integer objective; and analyte_membership,
an object mapping each analyte to its tier.

analyte_totals.json is an object mapping each analyte that appears in
analyte_allocations to its integer total, and the analyte_membership objects and
tier_analyte_membership.json cover those same analytes. Both class_totals objects,
like tier_totals, hold only the matrices or tiers those same analytes belong to.
tier_analyte_membership.json is an object mapping each analyte to its tier.
ordered_reading_index.json is the list of reading ids in processing order.
excluded_readings.json is the same sorted list of qc-fail excluded reading ids.

analyte_committed.csv is comma separated with the header line
analyte,matrix,tier,committed_total and one row per analyte of the crosswalk sorted by
analyte. batch_committed.tsv is tab separated, its header line included, with the
columns batch, committed_total and convergence_rounds and one row per batch sorted by
batch. matrix_weighted.psv is pipe separated, its header line included, with the
columns tier, committed_total, tier_weight and weighted_contribution and one row per
tier of the tier weight book sorted by tier.

carryover_ledger.xml is written line by line. The first line is the declaration
<?xml version="1.0" encoding="UTF-8"?>
and the second line opens the carryover_ledger root element. Then comes one line per
clawback, in carryover_ledger order, holding two spaces and a self-closing entry element
whose attributes are batch, analyte and clawed_units in that order. Then comes a line
holding two spaces and a self-closing total element whose one clawed_units attribute is
the summed clawback, and the last line closes the root element. Attribute values are
double quoted and XML escaped, with one space between attributes and none before the
closing slash.

objective_summary.yaml has one key per line, written as the key, a colon, a space and the
value: objective_value, committed_grand_total, excluded_count, carryover_total_units,
effective_lot and core_sha256 in that order, then the line tier_totals: and one line per
tier of the tier_totals object sorted by tier, indented by two spaces.

reconciliation_report.md opens with this exact title line:
# Assay QC Reconciliation Report
then a blank line, then the objective_value, committed_grand_total,
effective_lot and excluded_count lines, then a blank line, then this exact heading:
## Batch totals
then a blank line, then one bullet per batch sorted by batch written
as a hyphen, a space, the batch key, a space and the committed total. run_status.txt
lists status, objective_value, core_sha256 and unsettled_batches in that order, where
status is the word SETTLED when no batch is unsettled and the word UNSETTLED
otherwise, and unsettled_batches is the word none when no batch is unsettled and the
unsettled batch keys joined by a comma otherwise. In both of these two files a line
pairs its key and value with a single space and no colon, unlike objective_summary.yaml
which pairs them with a colon and a space. Every line in both files ends with a single
newline, and so does every line of the csv, tsv, psv, xml and yaml artifacts, the last
line included, with no blank line after it.

provenance_manifest.json is an object with keys artifact_names, the sorted list of
every report filename the program writes into the output directory, including
provenance_manifest.json itself and leaving out the program derive_report.py; core_files, the
three core files in order; core_sha256, the digest; and reusable_program, the string
/app/out/derive_report.py.

The digest core_sha256 is the sha256 hex of the concatenation, in the core_files
order, of the exact serialized bytes of summary.json, then policy_audit.json, then
panel_analyte_glucose.json, each serialized as sorted-key compact JSON with its
trailing newline, with no separator between them.
