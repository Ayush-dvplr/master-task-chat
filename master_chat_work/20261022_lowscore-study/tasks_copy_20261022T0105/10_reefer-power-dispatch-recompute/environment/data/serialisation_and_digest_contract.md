# Serialisation and digest contract

Every published document is written as utf-8 with a line feed as the
line ending and no carriage return anywhere. Every document ends
with exactly one line feed and carries no blank line before it.

A delimited document writes its header once as the first line. A
field is never quoted and never carries its own delimiter.

A document with no data row is written as its header line alone.

Every object document is written with an indent of two spaces, the
keys in the order the output schema reference prints them, and a
single line feed after the closing brace. A key is followed by a
colon and one space, an item closes a line with a bare comma, and
an empty object or list is written on one line as {} or [].
Key order is the written order and is never sorted.

Every line delimited object document writes one object per line with
no space after a comma or a colon, the keys in the order the output
schema reference prints them, and one line feed after the last
object.

An extensible markup document opens with the line
<?xml version="1.0" encoding="utf-8"?>, indents every nesting
level below the root element by two spaces, and writes an element
carrying no child as one self closing tag.

A free text document writes each of its paragraphs on a single
line and never wraps one. worked_examples.md wraps its own lines
to the width of the page and that wrapping is no part of the
shape it fixes.

A whole quantity is written as a whole number. A ratio is written at
exactly nine decimal places. Money is written in whole cents. Power
is written in whole watts and energy in whole watt hours. Negative
zero is never written.

## The two digests

publication_manifest.json carries a core digest and a publication
digest.

The core digest is the sha256, in lowercase hexadecimal, of the
bytes of the six core documents concatenated in this order:
normalised_reefers.jsonl, energy_floor_ledger.csv,
provisional_allocation.psv, reconciliation_iterations.csv,
objective_vector.json, final_schedule.csv.

The publication digest is the sha256 of the bytes of every other
published document concatenated in the order the documents list of
the manifest prints them, with the six core documents and the
manifest itself left out.

The documents list carries every published document except the
manifest, in this order.

First the fourteen stage documents, one for each stage in stage
order: normalised_reefers.jsonl, availability_lattice.csv,
energy_floor_ledger.csv, dispatch_priority_queue.csv,
provisional_allocation.psv, feeder_violation_ledger.csv,
crane_adjusted_capacity.csv, battery_schedule.csv,
reconciliation_iterations.csv, tariff_charge_ledger.csv,
deadline_correction.csv, cycle_break_report.json,
objective_vector.json and final_schedule.csv.

Then the load family: interval_demand.csv,
feeder_load_ledger.csv, spill_decisions.tsv, soc_ledger.psv and
constraint_certificate.json.

Then the tariff family: peak_demand_certificate.json,
unmet_requirement_report.tsv, reefer_service_certificate.csv,
audit_trace.jsonl and dispatch_control_totals.conf.

Then the publication family: final_schedule_by_feeder.psv,
final_schedule_by_vessel.xml, one substation report for each
substation the reporting roster publishes in the order that
roster prints them, and daily_dispatch_summary.md.

Each entry carries the document name, its length in bytes and the
sha256 of its bytes.
