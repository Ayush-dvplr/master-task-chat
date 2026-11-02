# household assistant reminder surface authority policy

## Scope

This policy governs the reminder surface of the release train. It is binding on
every layer that claims to describe the surface, and on every account of a
surface incident.

## Authority

The change ledger is the only authority for the reminder surface. It is
stored as shards: the ledger is the union of the records in every file
directly inside `ledger/` whose name starts with `shard_`, whatever its
format (`.csv` comma separated, `.psv` pipe separated, `.ndjson` one JSON
object per line). Each delimited shard starts with a header row, and the
column order differs between shards, so a field is read by its header name.
Delimited shards carry every field as text; `seq`, `value`, `authority_rank`
and `effective_generation` are integers. A record sequence may be re-exported in more than one shard; the copy in the
shard whose file name sorts last governs and the other copies are ignored.
Every text evidence file is UTF-8 and may begin with a byte order mark, which
is not part of its content, and a delimited header name is read without its
surrounding whitespace. `ledger/archive/` holds a retired export from before the current
release cycle and is not part of the ledger. Every other file that names a scope, a value, a digest or a
household version is a derived layer. A derived layer is evidence about the
past, never a source of truth about the present.

## Sources and precedence

The rules of this document are amended by the policy addenda
`policy_addendum_A<n>.docx`. An addendum overrides this document and
`urgency_class_catalogue.json` on every rule it amends, and where two addenda
amend the same rule the addendum with the higher number governs.
`scope_authority_policy_v1.md` is the superseded first edition of this
document and binds nothing.
Where this document and `urgency_class_catalogue.json` disagree, this
document governs: the household version fold and the recovery tie rule name
the classes they apply to, whatever class ranks or fold labels the catalogue
prints.

The release operations journal is the table `journal` of the SQLite database
`release_ops.sqlite`; journal line order is the order of its `line_no`
column. The table `journal_staging` in the same database holds operations the
release desk has not filed and is not part of the journal.

The restricted scope map is the sheet of `restricted_scope_map.xlsx` whose
name starts with `active_`; its columns are read by their header names.
Sheets whose names start with `draft_` hold proposals and resolve nothing.

The deprecation window and the urgency weights are published nowhere: the
catalogue value and addendum A1 are void, and `urgency_weights.draft.yaml`
was never adopted. Both are recovered from the calibration controls under
`calibration/` as the parameter recovery section below describes.

`generated_scope_snapshot.prev.json` is an earlier compile of the snapshot
and is not one of the derived layers this document introduces.

## Derived layers

Downstream teams meet the surface from the consumer end, so the derived layers
are introduced here in that order. The coverage gate report
`coverage_gate_report.json` is the release gate that claims the platform is
consistent. The builder runtime state `assistant_runtime_state.json` records
which surface the running builder loaded. The household index
`household_index.json` groups the exported scopes into households and is
built from the snapshot. The generated export snapshot
`generated_scope_snapshot.json` is what the release train compiler produces
from the ledger. Every account names a layer by its bare file name and names
the authority itself as `ledger/`.

## Replay order

The authority replay walks the ledger ordered by effective generation
ascending, and by record sequence ascending inside a single effective
generation. This composite ordering key is written `effective_generation,seq`
whenever an account has to name it. Record sequence alone is a different
ordering key, written `seq`, and it is the ordering key of the control replay
defined below. The two orderings select a different record as the final state
of a scope whenever a lower generation was recorded after a higher one.

## Record semantics

Each ledger record carries a record sequence, a scope, an operation, a value,
an urgency class, an authority rank, a reference domain, a lineage anchor, an
effective generation and a recorder. The operations are as follows.

A `publish` record admits a scope to the active surface with its value. A
publish that names a scope already active, or already retired, changes
nothing.

A `revise` record replaces the value of an active scope. A revise that names
a scope which is not active changes nothing, and so does a revise whose
value, once resolved, is the value the scope already carries at that point
of the replay.

A `deprecate` record opens a deprecation on an active scope and records the
authority rank and the effective generation of that deprecation. Deprecations
stack, so a scope may carry more than one open deprecation.

A `restore` record closes the most recent open deprecation of its scope when
the authority rank of the restore is greater than or equal to the authority
rank of that deprecation. When the authority rank of the restore is lower, the
restore changes nothing and the deprecation stays open.

A `withdraw` record removes a scope from the active surface, appends it to
the retired list, and discards every open deprecation on it. A withdrawn
scope never returns.

A record that changes nothing is inert. Inert records are still parsed, still
counted in the ledger, and are excluded from the effective record set.

## Inert reasons

Every inert record carries exactly one reason from this closed set, tested in
this order so that the first reason that applies is the one reported:
`rolled_back` (a non rejected `rollback_change` names the record),
`apply_change_rejected` (every `apply_change` naming the record is rejected),
`publish_names_known_scope`, `revise_names_inactive_scope`,
`revise_keeps_value` (the resolved value equals the current value),
`deprecate_names_inactive_scope`, `restore_without_open_deprecation`
(the scope is not active or carries no open deprecation),
`restore_rank_below_deprecation` and `withdraw_names_inactive_scope`.
The inert record list holds one object per inert record, with exactly the
keys `seq` and `reason`, ordered by record sequence ascending.

## Reference domains

A record whose reference domain is `scope_id` carries its value
literally. A record whose reference domain is `restricted_scope_index`
carries an alternate key rather than a value, and the value must be resolved
through the restricted scope map by matching both the alternate key and
the lineage anchor. Alternate keys repeat across rows, so the lineage anchor
is what settles the row.

A record whose lineage anchor is `pending` has no anchor of its own yet. The
release operations journal carries `supersede_anchor` operations for that
scope, each naming a retired anchor and a surviving anchor. The anchor that
resolves the record is the surviving anchor of the last `supersede_anchor`
operation for that scope, in journal line order, whose status is not
`rejected`. A rejected supersede settles nothing, wherever it sits in the
journal.

A lineage anchor written on a record is read literally only while no
`supersede_anchor` operation of the record's own scope that is not rejected
names it as its retired anchor. Once one does, the record resolves exactly as
a pending record of that scope does.

## Journal replay

The release operations journal carries release operations. An operation
whose status is `applied` has already been folded by the builder runtime and
an operation whose status is `pending` has not; both belong to the journal
view and take part in every replay in exactly the same way. An operation whose
status is `rejected` was refused by the release desk and takes part in no
replay at all.

A ledger record that no `apply_change` operation names is admitted on its own.
A ledger record that one or more `apply_change` operations name is admitted
when at least one of those operations is not rejected; a record whose every
`apply_change` operation is rejected is inert. A `supersede_anchor` operation
settles a pending lineage anchor as described above. A `rollback_change`
operation that is not rejected withdraws the ledger record it names from the
effective record set, and that record is inert.

## Deprecation window

The deprecation window, in generations, is the window recovered under
parameter recovery. A scope that still carries an open deprecation once the replay
has finished is measured against its most recent open deprecation, the one a
restore would close next. It leaves the active surface and joins the retired
list when the difference between the surface generation and the effective
generation of that deprecation is greater than or equal to the window. A
scope whose most recent open deprecation is younger than the window stays
active.

Scopes withdrawn during the replay join the retired list in replay order.
Scopes that the window retires join it after all of them, ordered by the
effective generation of the deprecation that retired them ascending, and by
scope name ascending where two share that generation.

## Surface generation

The surface generation is the largest effective generation recorded on any
ledger record, whether or not that record turned out to be effective.

## Release version fold

The household version starts at `0.0.0` and folds one step for every effective
record, taken in authority replay order. A `breaking` class increments the
major component and resets the minor and patch components to zero. An
`additive` class increments the minor component and resets the patch component
to zero. An `internal` class increments the patch component. Inert records do
not fold. The version is reported as three integers joined by dots.

## Urgency totals

The urgency totals count the ledger records of each urgency class, effective
and inert alike, because they describe what the recorders wrote. Every class
the catalogue publishes appears as a key, with zero when no record carries it.

## Parameter recovery

`calibration/published_controls.psv` lists calibration controls, one per
line, with the columns `control`, `retired_scopes` and `urgency_grand_total`.
Each control's ledger is `calibration/<control>.ndjson`, with the same record
fields as the ledger. `retired_scopes` is the control's retired list in
retirement order, names joined by `;`, or `-` when it is empty.

A control is replayed under the authority ordering with the record semantics
and the deprecation window rule of this document, with no journal (every
record is admitted and every reference domain is `scope_id`), and with the
control's own largest effective generation as its surface generation. Its
grand total is the sum, over every record of the control, of the urgency
weight of the record's class.

A candidate is a deprecation window, an integer from 2 to 30, together with
an urgency weight for each catalogue class, each an integer from 1 to 99. A
candidate fits when every control, replayed with it, yields exactly the
published retired list and the published grand total. The controls are read
in file order and a candidate that fits the first control can still fail a
later one. When several candidates fit every control, the one in force has
the largest window and, separately, the largest `breaking` weight, then the
largest `additive` weight, then the largest `internal` weight. The window is
settled by the retired lists alone and the weights by the grand totals alone.

## Surface digest

The surface digest is the sixteen character hexadecimal digest produced by
BLAKE2b with an eight byte digest size over the UTF-8 encoding of the compact
JSON serialization of the active surface, where the serialization sorts keys
and uses no whitespace after the separators. `scope_conformance_fixtures.json`
carries a worked digest over a two scope surface so that an implementation can
be checked before it is trusted.

## Control replay

The control replay rebuilds the whole surface a second time from the same
ledger and the same journal view, with every rule of this policy unchanged
except the ordering key, which is record sequence ascending. It produces a
control digest under the same digest rule. The control replay is a diagnostic
and never a source of truth. Reporting one digest in both the surface digest
field and the control digest field is a reporting fault.

The first divergent record is found by laying every ledger record, effective
or inert, out under both ordering keys and walking the two sequences position
by position. At the first position where they hold different records, the
first divergent record is the one the authority ordering places there, and it
is reported by its record sequence.

## Divergence

A scope diverges in a derived layer when the authority surface carries it and
the layer carries a different value for it. The pre repair divergence count
is the number of scopes on which the generated export snapshot diverges from
the authority surface, which is also the number of entries in the minimal
delta. The post repair divergence count compares the recovered surface with
the authority surface.

## Rank total order

The rank total order sorts the active scopes by value descending and by
scope name ascending where two scopes carry the same value.

## Transitions

A transition identifier is the literal `seq`, the record sequence, the scope
and the operation of an effective record, joined by colons, so that record
sequence 7 publishing `alpha` reads `seq:7:alpha:publish`. The transition
list is the identifiers of every effective record in authority replay order.

## Revisited anchors

The revisited anchor list holds one object per effective record whose
reference domain is `restricted_scope_index`, in authority replay order, with
exactly the keys `seq`, `scope`, `lineage_anchor` (the anchor that resolved
the record, after settlement) and `canonical_value` (the value the map row
supplied). Inert records are not revisited.

## Candidate causes

`urgency_class_catalogue.json` publishes a closed set of candidate causes.
Exactly one candidate cause is supported by the evidence. Each cause has one
falsifier, an observation that rules it out when it holds:

- `compiler_ordering_key`, the compiler walked the ledger under an ordering
  key other than the authority key, is falsified by
  `authority_replay_digest_matches_snapshot`.
- `journal_backlog`, the snapshot was compiled without the journal view, is
  falsified by `control_replay_digest_matches_snapshot`, since the control
  replay carries the full journal view.
- `restricted_anchor_ambiguity`, a restricted reference resolved to the wrong
  map row, is falsified by `anchor_examples_reproduce`.
- `runtime_restart_pending`, the runtime serves a surface older than the
  snapshot, is falsified by `runtime_digest_matches_snapshot`.

An account names the supported cause through the layer and the ordering key
it observed, and names as its rejected hypothesis the one candidate cause that
the control replay falsifies, together with that falsifier.

## Preservation

The ledger shards, the journal database, the restricted scope workbook, the
addenda, the catalogue and every other file under the evidence directory are read only. A recovery that edits
them is void. Retired scopes are preserved in the retired list in the order
in which they were retired.

## Serialization

Every JSON artifact is written as UTF-8 with two space indentation, line feed
line endings and a trailing newline. Integers are written as integers. No
floating point value appears in any artifact.

## Determinism

Running the recovery twice produces byte identical artifacts. Deleting the
derived layers and running the recovery again rebuilds them from the ledger
alone.
