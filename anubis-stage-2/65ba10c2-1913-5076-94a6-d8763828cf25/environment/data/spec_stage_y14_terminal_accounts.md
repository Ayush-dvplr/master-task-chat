STAGE Y14  Terminal accounts and publication
shift KP-2042-S23

This stage closes the accounts. Every figure here is read off the
ledgers the earlier stages published and none of it is derived a
second time from the source papers.

RULE Y14.1  The control totals.
The measures published in terminal_reconciliation.csv are the ones
output_schema_reference.md names, in ascending measure name.

RULE Y14.2  The identity checks.
Totals that agree by category can still disagree by identity, so
each check compares the identity sets and not the counts. The
checks are the four output_schema_reference.md names, and each
publishes yes or no.

RULE Y14.3  The reports.
One report is published for each berth of
berth_reporting_roster.conf, whatever it rationed, a berth that
rationed nothing included.

RULE Y14.4  The digests.
publication_manifest.json carries a digest of every document
beside it. The core digest covers the six core documents
output_schema_reference.md names and the publication digest
covers every other document of the publication. Both are taken
over lines of document name, one space and the document digest, in
the artifact order the schema reference lists, each line ending
in one line feed. The digests are taken last, after every other
document is written.

PUBLISHES  terminal_reconciliation.csv, exception_summary.tsv,
vessel_reconciliation.xml, audit_trail.conf, the berth reports,
daily_operational_summary.md, final_control_totals.json,
publication_manifest.json
