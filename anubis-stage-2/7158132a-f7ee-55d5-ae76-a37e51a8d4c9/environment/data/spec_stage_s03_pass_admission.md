# S03 pass admission

Each row of pass_plan_of_record.csv is tested against eight predicates
in the order below. The first predicate that fails decides the
rejection, and the later predicates are not evaluated. The recorded
predicate_index is the one based position of the failing predicate.

| index | code | predicate |
| --- | --- | --- |
| 1 | E01 | the presentation_id resolves to a mission at scheduled_start_s |
| 2 | E02 | station_id with aperture_label resolves to a current aperture |
| 3 | E03 | the station lies in the scope of at least one contract of the mission that is valid at scheduled_start_s |
| 4 | E04 | the mission campaign phase covering scheduled_start_s is not a standdown |
| 5 | E05 | no effective cancellation lands strictly before the commit boundary |
| 6 | E06 | the journal carries an operational event for the pass |
| 7 | E07 | the event_status is nominal or partial |
| 8 | E08 | the clipped eligible interval carries seconds, or the pass is zero length and its instant is available |

## contract validity and scope

A contract is valid at an instant when valid_from_s is at or before it
and valid_to_s is strictly after it. The contracts of a pass are every
contract of the pass mission that is valid at scheduled_start_s and
whose station_scope contains the station of the pass. If that set is
empty the pass fails predicate three.

## campaign phase

campaign_schedule.xml carries one phase element per mission per
phase_seq, each a half open interval [phase_from_s, phase_to_s). The
phase of a pass is the one containing scheduled_start_s. A pass in a
standdown phase fails predicate four. routine, intensive and
commissioning phases all admit.

## the commit boundary

The commit boundary of a pass is its scheduled_start_s less the commit
lead of its station. The commit lead is published per station in
network_operations_memo.pdf and appears in no other file.

## cancellations

cancellation_notices.csv carries one row per notice. Several notices may
name the same pass. Order the notices of a pass by issued_seq. The
binding notice is the last one whose notice_state is effective. A pass
with no effective notice was never cancelled. A rescinded notice binds
nothing, including when it is the last notice by issued_seq.

A binding notice whose effective_s is strictly before the commit
boundary rejects the pass at predicate five. A binding notice whose
effective_s is at or after the commit boundary does not reject it: the
pass stays admitted and carries late_cancel set to one. A notice landing
exactly on the commit boundary is a late cancellation, not a rejection.

A cancelled pass is rejected whether or not the journal recorded an
operational event for it. The presence of an event resurrects nothing.

## the operational event

contact_event_journal.ndjson carries at most one event per pass. A pass
with no event fails predicate six. An event whose event_status is
aborted or no_show fails predicate seven.

## the reject ledger

Every rejected pass is written to the rejected ledger once, with its
code, its reason and its predicate_index. A rejected pass appears in no
later ledger.
