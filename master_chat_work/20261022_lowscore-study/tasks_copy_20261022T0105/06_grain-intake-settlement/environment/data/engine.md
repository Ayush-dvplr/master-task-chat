# The intake settlement engine

This directory holds intake shifts from a country grain elevator and what the
settlement engine made of them. The engine was lost when the scale house was
recabled. Its file shapes and its stage order are written down here. Its numbers
are not, and neither is the meaning of its mode word.

## What ships here

An intake is seven files under one prefix. The graded intake carries no prefix at
all.

| File | One row per | Columns |
|---|---|---|
| `manifest.json` | the intake | see below |
| `dryers.csv` | dryer | `dryer`, `make`, `tare_base` |
| `contracts.csv` | grain contract | `contract`, `family`, `lots` |
| `graders.csv` | scale house grader | `grader`, `role` |
| `haulers.csv` | hauling outfit | `hauler`, `class` |
| `bins.csv` | bin | `bin`, `dryer`, `contract`, `commodity`, `tier` |
| `tickets.jsonl` | scale ticket | `seq`, `bin`, `card`, `grader`, `hauler`, `action`, `gross`, `testweight` |

`tickets.jsonl` is stored in an arbitrary line order.

`commodity` is one of `wheat`, `barley`, `canola`, `oats`, `corn`, `milo`, `rye`,
in that order. `family` is one of `basis`, `track`, `board`, `hedge`. `role` is
one of `weighman`, `inspector`, `apprentice`, `relief`. `class` is one of `line`,
`custom`, `spot`. `tier` is 1, 2 or 3. `action` is one of `weigh`, `tare`,
`settle`, `void`.

`manifest.json` carries `intake`, `mode`, `declared_tickets`, `bin_digests` and
`run_digest`. `declared_tickets` is the number of lines in `tickets.jsonl`, every
line counted, whatever screening later makes of it. The two digest fields are
defined in `reports.md`.

## Intake screening

The link between the scale house and the engine was never reliable, so
`tickets.jsonl` can carry lines that were sent twice, lines that disagree with
each other, and lines that were damaged on the way. Before anything else runs the
engine screens every line of the file. Screening is the same at every mode word:
no mode bit changes it, and the chain below only ever sees the tickets screening
keeps.

A line is split off at each newline byte. A line holding nothing but whitespace is
skipped and is not a ticket. Screening then runs in three passes.

**Pass one** looks at each line on its own and sets it aside as damaged when any
of these holds:

- its bytes are not valid UTF-8, or the text is not one JSON object;
- the object names the same key more than once, whatever the values written
  against it and whether or not that key is one of the eight;
- any of the eight ticket keys is missing;
- `action`, `bin`, `card`, `grader` or `hauler` is not a JSON string;
- `seq` is not a JSON integer of at least 1, `gross` is not a JSON integer of at
  least 0, or `testweight` is not a JSON integer of at least 1. JSON `true` and
  `false` are not integers, and neither is a number written inside a string or a
  number written with a fraction or an exponent, such as `412.0` or `412e0`, even
  when its value is whole;
- `action` is not one of the four actions;
- `bin` is not a bin in `bins.csv`, `grader` is not a grader in `graders.csv`, or
  `hauler` is not a hauler in `haulers.csv`.

Apart from the repeated key test above, keys beyond the eight are ignored, and so
are the order of the keys and the spacing between them. A value is what the JSON text denotes, not how it is
spelled: a string written with `\u` escapes carries the same value as the same
string written out plainly.

**Pass two** takes the lines that survived pass one and groups them by `seq`.
When every line in a group carries the same eight values, the group is one ticket
sent more than once: unless pass three sets it aside, it resolves once and every
copy past the first is a retransmission. When the lines in a group disagree on
any of the eight values, the `seq` is in conflict and every line in that group is
set aside, however many of them agree with each other. A damaged line never takes
part in pass two, so it cannot put a `seq` in conflict.

**Pass three** settles each scale card once per bin. It walks the groups pass two
let through, in ascending `seq`, and the first of them to carry a given pair of
`bin` and `card` claims that pair. A later group carrying a pair already claimed
is a re-entry: every line of that group is set aside, its copies included, and
none of them counts as a retransmission. A `seq` that pass two put in conflict
claims nothing, so it never makes a later group a re-entry.

A line that is set aside is never resolved, never reaches a report line, and
changes no carried value. `elevator.json` counts what screening did; see
`reports.md`.

## The mode word

`mode` is a thirteen bit word, from `0x0001` to `0x1000`. Every bit is defined,
and each one switches on a single alteration somewhere in the chain below: to
what a stage reads, to what it carries, to which tickets it walks, or to how a
rollup is totalled. Each bit acts independently of the others, and setting one
never turns another off.

What any individual bit does was recorded only in the scale house firmware, and
that firmware is gone. Nothing in this directory says which bit is which.

The graded intake in this directory has every bit set. Two worked intakes ship
under the prefixes `example_a_` and `example_b_`, and both have `mode` of zero:
they carry no alteration at all and are there to pin down the chain below. Each
of them ships with the three files the engine wrote for it, named
`example_a_out_settlements.jsonl`, `example_a_out_binroll.json` and
`example_a_out_elevator.json`, and the same three under `example_b_`.

## Carried bin state

Each bin carries three values while its tickets are resolved.

- `tare level`: at mode zero it starts at the `tare_base` of the bin's dryer.
- `dockage`: starts at zero.
- `strike count`: starts at zero.

## The chain at mode zero

At mode zero the engine resolves the screened tickets in ascending `seq`, a single
intake wide ordering across every bin, and passes each ticket through these stages in this
order. Every figure is a whole number of unbounded size and no stage routes one
through a fractional type, so a load far larger than a 64 bit float holds exactly
still settles to the last bushel. No stage reports a figure below zero: each one
clamps its result at zero before the next stage runs.

1. **Tare.** The bin's current tare level is taken off the ticket's `gross`.
2. **Testweight normalisation.** The figure is rescaled against the ticket's
   `testweight` with one fixed factor, and the division truncates towards zero.
3. **Commodity adjustment.** One adjustment keyed on the bin's `commodity`. Six
   of the seven commodity values carry an adjustment; the seventh leaves the
   figure alone.
4. **Contract adjustment.** One adjustment keyed on the contract's `family`.
   Three of the four families carry an adjustment; the fourth leaves the figure
   alone.
5. **Dockage deduction.** The bin's dockage at the moment the ticket is resolved
   is taken off the figure. That dockage is reported as `dockage_before` and the
   result is reported as `bushels`.
6. **Banding.** `bushels` falls into one of four bands, reported as `band`:
   `prime`, `mill`, `feed` or `scrap`, from the widest figure down.
7. **Status.** An ordered ladder decides `status`. The first condition that holds
   wins and the rest are never consulted.
   - an opening action resolves to `open`;
   - a voided ticket resolves to `voided`;
   - a bottom band ticket resolves to `rejected`;
   - a ticket whose `dockage_before` sits above the tolerance of the grader's
     `role` resolves to `flagged`, and each of the four roles has its own
     tolerance;
   - anything left resolves to `clear`.
8. **Carry update.** After the settlement is emitted the bin state moves on. A
   `tare` ticket replaces the tare level. A `settle` ticket clears the dockage. A
   `weigh` ticket adds a dockage charge derived from its `testweight`, and one of
   the three `tier` values changes the size of that charge. Dockage has a ceiling
   it never passes. A `rejected` ticket adds one strike.

## What is missing

The normalisation factor, the six commodity adjustments, the three contract
adjustments, the three band edges, the four role tolerances, the dockage charge,
the tier that changes it, the dockage ceiling, the strike count that embargoes a
bin, the dockage figure that holds a bin back, which statuses count into a bin
total, and both of the tie breaks in `reports.md` are firmware constants. The two
mode zero intakes and their outputs are the evidence for those.

The thirteen mode bits have no worked intake at all. The digests in
`manifest.json` are the only thing that says whether a reading of them is right.
