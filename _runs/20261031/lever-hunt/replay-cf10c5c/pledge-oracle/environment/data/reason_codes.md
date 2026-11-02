# Reason codes

A pledge in an artifact carries a list of reason codes drawn from this closed set.
The list is sorted as text and holds no repeats. A pledge with nothing to report
carries an empty list.

| code | attaches when |
| --- | --- |
| ack_supersedes_register | the governing due record came from counterparty_ack while a surviving register amendment also spoke about the pledge |
| class_ceiling_binding | the grace round held the grant of the pledge at the smaller of its lateness and its class ceiling, so the raw share was cut back |
| counterparty_dissolved | the holder of the pledge carried a dissolved status at the governing due instant |
| cycle_held | the pledge sits in a group of pledges that depend on each other |
| late_evidence | the effective instant of the pledge falls after its governing due instant |
| no_evidence | the pledge has neither governing discharge evidence nor a governing waiver |
| prereq_lapsed | a prerequisite of the pledge is lapsed |
| prereq_pushed | a prerequisite contribution set the effective instant of the pledge later than its own evidence |
| prereq_unsettled | a prerequisite of the pledge is unsettled |
| series_shifted | the pledge is a series instance whose period carried a shift action |
| waiver_applied | the pledge was settled by a waiver grant |
| waiver_late | the waiver that settled the pledge was granted after the governing due instant |
