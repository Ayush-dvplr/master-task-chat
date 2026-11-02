# S14 reconciliation emission

S14 writes the artifacts. It computes nothing that the earlier stages
did not already freeze, except the three reports below.

## the discrepancy report

cross_source_discrepancy_report carries two families.

The first compares the canonical ledger against downlink_reports.csv.
For each pass with at least one accepted canonical row, the left value
is the sum of its accepted_kib across periods and the right value is the
reported_kib of its binding report, which is the report with the highest
report_seq. Rows that agree are not reported. discrepancy_class is
over_report when the report is larger and under_report when it is
smaller. source_left is canonical_ledger and source_right is
downlink_report. period_id is empty for this family because the
comparison is over the whole pass.

The second compares the effective rate schedule against
legacy_flat_rate_table.csv. For each aperture, take the binding legacy
row, which is the one with the highest table_rev. When its flat rate
lies inside the closed band from the smallest to the largest effective
rate of that aperture, nothing is reported. When it lies outside, the
left value is the nearer end of the band, the right value is the flat
rate, and discrepancy_class is retired_rate_outside_band. source_left
is rate_schedule and source_right is legacy_flat_table.

The four source slugs are written exactly as given here. They name the
side of the comparison and are not the file names of the papers the
sides were read from.

Rows are ordered by source_left then subject_id.

## the invariant report

A fixed list of balance checks, each carrying a left value, a right
value and whether they matched. The checks and their order are in
output_schema_reference.md. all_balanced is one when every check
matched.

## the exception report

One record per exception, drawn from the admission rejections, the
capacity cap clippings, the displacements, the carry forfeits, the empty
utilisation denominators and the late cancellations. Codes are in
exception_code_dictionary.xml. Ordered by exception_class, then
subject_id, then code, then the period the exception arose in, P1
before P2 before P3. Two exceptions that share a class, a subject and
a code always arose in different periods, so that fourth key settles
every tie. The period is a sort key only and is not a field of the
record.

## the digest manifest

stage_digest_manifest.json carries the count of core artifacts, the
sha256 of each of them, and core_digest, which is the sha256 of the
concatenation of the core artifact bytes in the order given by
output_artifact_contract.md. The manifest is not part of the
concatenation.
