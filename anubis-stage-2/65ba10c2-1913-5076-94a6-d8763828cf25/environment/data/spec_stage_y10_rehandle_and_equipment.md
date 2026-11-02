STAGE Y10  Rehandles and equipment
shift KP-2042-S23

This stage derives the rehandles and charges the equipment. Both
are read off the state this shift produced, not counted off the
source journals.

RULE Y10.1  What a rehandle is.
An admitted order is a rehandle when the box it moves was
standing in a yard cell immediately before that order. An order
that puts a box on the yard for the first time is a placement and
not a rehandle. The rehandle count of a box is the number of its
admitted orders that were rehandles, and it is derived from the
state history and not from any count the source papers carry.
The rehandle ledger carries one record per box that the state
history holds at least one admitted order for. A box no admitted
order moved has no record in it at all.

RULE Y10.2  The charge.
Every admitted order carries the base move charge issued by the
live workbook sheet. A rehandle carries, on top of that, the
surcharge its tier depth attracts.

RULE Y10.3  The tier depth.
The tier depth of a rehandle is the tier the box was standing at
before the order, not the tier it moves to.

RULE Y10.4  The surcharge ladder.
The ladder is issued by berth_operations_memo.pdf and is carried
in no other paper. The surcharge of a depth is the surcharge of
the highest rung at or below that depth. A depth beyond the last
rung carries the surcharge of the last rung. A depth of one
carries no surcharge.

RULE Y10.5  The equipment allowance.
The applicable revision of an equipment unit is settled through
revision_precedence.toml. Confirmed movements are charged to the
unit their confirmation names, in ascending event key. A unit
that has carried exactly its allowance is inside it. The movement
that would take a unit one past its allowance is recorded as an
equipment exception and is charged to nothing, and so are the
movements after it. A confirmation naming a unit with no
applicable revision is an exception of its own kind.

RULE Y10.6  A unit that carries nothing.
A unit whose allowance is zero is published with a used count of
zero, and so is a unit no movement was charged to. Both are
published; a unit the register does not carry is not.

RULE Y10.7  What the equipment usage document publishes.
The used figure of a unit is the count of movements charged to
it. The minutes figure is that used count multiplied by the base
minutes its applicable revision declares, so a unit charged no
movement publishes zero minutes whatever its base minutes say.
The within_allowance figure reads yes whenever the used count is
at or below the allowance. A unit that turned a movement away at
RULE Y10.5 still reads yes, because the movement it turned away
was never charged to it and its used count never passed the
allowance.

PUBLISHES  rehandle_ledger.jsonl, equipment_usage.csv,
equipment_exceptions.tsv
