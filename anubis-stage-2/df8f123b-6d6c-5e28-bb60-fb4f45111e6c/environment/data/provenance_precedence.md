# Provenance precedence

Every record in the corpus belongs to one source. source_manifest.md names the
source of each file. A record speaks about one field class.

| field class | source order |
| --- | --- |
| due_instant | counterparty_ack, register, inbox_thread |
| discharge_evidence | register, counterparty_ack, inbox_thread |
| waiver | counterparty_ack |

Records from the voice_memo source are advisory. They are retained for reference
and they never govern a field class.

A record is surviving when its effective instant and its logging instant both
fall at or before the settlement cutoff and no live retraction notice names its
record key. A retraction notice is itself a record and can be named by another
retraction notice; a notice that is named by a live notice has no effect.

For one pledge and one field class the governing record comes from the highest
ranked source in the order above that holds any surviving record. Lower ranked
sources are then set aside however recent they are. Within the governing source
the record with the latest effective instant governs.

Competing records inside the governing source can share an effective instant.
precedence_worked_cases.csv holds closed rulings for such groups, and
duplicate_record_audit.csv holds closed rulings where two records agree on every
dated field. Those rulings settle the remaining order.

The governing due record supplies both the due expression and the authority that
the artifact reports. The authority is the source name of the governing record.
When no surviving amendment speaks about a pledge, the register entry itself is
the authority and its record key is reported.
